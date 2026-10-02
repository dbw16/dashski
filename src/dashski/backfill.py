"""One-shot backfill of past advisories from the NZAA's forecastsearch endpoint.

The live source only ever sees the two most recent advisories per region, so the
history slider starts wherever the DB does. This walks backwards from there,
using the one endpoint that answers for a past date (`fetch_history`).

`--days` names the target — N days before today — not an increment: each run
walks each region's frontier back to that date, resuming from what is already
stored, so a run that dies partway through costs only the days it hadn't
reached and rerunning with the same `--days` finishes the job rather than
digging N days deeper. A region already reaching the target fetches nothing.

    python -m dashski.backfill --days 30 [--dry-run]

The frontier is per region, not global — a region we started tracking later has
its own gap, and a shared frontier would never fill it. The walk excludes the
frontier day itself, so a backfill only ever writes earlier than what we already
hold and never stores a second copy of a publication the live source caught
(ADR 0017, ADR 0018).
"""

import argparse
import time
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Engine
from sqlmodel import Session, col, func, select

from dashski import db
from dashski.models import AvalancheAdvisory, SourceKind, SourceStatus
from dashski.scheduler import already_stored
from dashski.sources.nzaa_advisory import (
    HISTORY_BEGINS,
    NZ,
    REGIONS,
    SOURCE_ID,
    Region,
    fetch_history,
)

DEFAULT_DAYS = 30

DEFAULT_DELAY = 0.25
"""Seconds between requests. The endpoint showed no rate limiting; this is manners."""


def frontier(session: Session, region: Region) -> date:
    """The NZ-local day this region's stored history currently reaches back to.

    Days are NZ-local because the source publishes and searches in NZ dates: an
    advisory issued 19:00 NZ belongs to that evening, not the UTC day it rolls
    into. With nothing stored for the region there is no gap yet, so we start today.
    """
    oldest = session.exec(
        select(func.min(col(AvalancheAdvisory.issued_at))).where(
            col(AvalancheAdvisory.source_id) == SOURCE_ID,
            col(AvalancheAdvisory.region) == region.name,
        )
    ).one()
    if oldest is None:
        return datetime.now(NZ).date()
    return oldest.replace(tzinfo=UTC).astimezone(NZ).date()


def days_to_fetch(start: date, until: date) -> Iterator[date]:
    """The days before `start`, newest first, back to `until` (inclusive).

    `start` itself is excluded — it is already stored, which is what made it the
    frontier — and days before HISTORY_BEGINS don't exist to fetch. Newest first
    so an interrupted run leaves the frontier contiguous instead of punching a
    hole the next run would skip over.
    """
    day = start - timedelta(days=1)
    while day >= until and day >= HISTORY_BEGINS:
        yield day
        day -= timedelta(days=1)


def backfill_region(
    session: Session, region: Region, start: date, until: date, *, delay: float, dry_run: bool
) -> tuple[int, int]:
    """Walk one region back from `start` to `until`. Returns (days fetched, advisories stored).

    Commits per advisory so a crash keeps everything up to that point. Most days
    store nothing: the endpoint answers with whatever advisory *stood* on that
    day, so a forecast that held over a weekend comes back once per day and an
    off-season stretch keeps returning the season's last one.
    """
    fetched = stored = 0
    seen: set[object] = set()
    for day in days_to_fetch(start, until):
        advisory = fetch_history(region, day)
        fetched += 1
        time.sleep(delay)
        if advisory is None:
            break  # before this region's records begin; earlier days are emptier still
        key = advisory.content_key()
        if key in seen or already_stored(session, advisory):
            continue
        seen.add(key)  # dry runs never commit, so the DB alone can't tell us we've seen it
        stored += 1
        if not dry_run:
            session.add(advisory)
            session.commit()
    return fetched, stored


def ensure_source_row(session: Session) -> None:
    """Advisories key off SourceStatus, which is missing in a DB the poller never ran on.

    Only the row itself — a backfill is not a Fetch Run and must not touch the
    fetch bookkeeping that drives staleness.
    """
    if session.get(SourceStatus, SOURCE_ID) is None:
        session.add(SourceStatus(source_id=SOURCE_ID, kind=SourceKind.ADVISORY))
        session.commit()


def run(engine: Engine, days: int, *, delay: float, dry_run: bool) -> None:
    until = datetime.now(NZ).date() - timedelta(days=days)
    with Session(engine) as session:
        ensure_source_row(session)
        total_fetched = total_stored = 0
        for region in REGIONS:
            start = frontier(session, region)
            fetched, stored = backfill_region(
                session, region, start, until, delay=delay, dry_run=dry_run
            )
            total_fetched += fetched
            total_stored += stored
            print(f"{region.name:16} back from {start}  fetched {fetched:4}  stored {stored:4}")
        print(f"{'total':16} {' ':15}  fetched {total_fetched:4}  stored {total_stored:4}")
        if dry_run:
            print("dry run — nothing written")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill past NZAA advisories.")
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help=f"backfill each region to this many days before today (default {DEFAULT_DAYS})",
    )
    parser.add_argument(
        "--delay", type=float, default=DEFAULT_DELAY, help="seconds between requests"
    )
    parser.add_argument("--dry-run", action="store_true", help="report without writing")
    args = parser.parse_args()

    engine = db.get_engine()
    db.init_db(engine)
    run(engine, args.days, delay=args.delay, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
