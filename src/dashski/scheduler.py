"""Wires registered sources through APScheduler: fetch → store raw → parse → store readings.

Each source's run is isolated: failures are caught and recorded on SourceStatus/FetchRun
(feeding the dashboard's staleness indicators) and never crash the scheduler or block
other sources.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from dashski.models import AvalancheAdvisory, FetchRun, RawFetch, Reading, SourceStatus, utcnow
from dashski.sources.base import Source


def already_stored(session: Session, reading: Reading) -> bool:
    """True when this exact advisory is already in the DB — a refetch of what we have.

    Compared against the versions of the same publication (same region, same
    issued_at), of which dedupe leaves at most a handful (ADR 0016). Backfill
    reuses this so a re-run stores nothing it already has.
    """
    existing = session.exec(
        select(AvalancheAdvisory).where(
            col(AvalancheAdvisory.source_id) == reading.source_id,
            col(AvalancheAdvisory.region) == reading.region,
            col(AvalancheAdvisory.issued_at) == reading.issued_at,
        )
    ).all()
    return any(row.content_key() == reading.content_key() for row in existing)


def run_source(source: Source, engine: Engine) -> bool:
    """Execute one fetch run for a source, recording success or failure. Returns success."""
    started = utcnow()
    with Session(engine) as session:
        status = session.get(SourceStatus, source.source_id) or SourceStatus(
            source_id=source.source_id, kind=source.kind
        )
        status.last_attempt_at = started

        error: str | None = None
        try:
            raw = source.fetch()
            raw_row = session.get(RawFetch, source.source_id)
            if raw_row is None:
                raw_row = RawFetch(source_id=source.source_id, fetched_at=utcnow(), payload="")
            raw_row.fetched_at = utcnow()
            raw_row.http_status = raw.http_status
            raw_row.payload = raw.text
            session.add(raw_row)

            for reading in source.parse(raw):
                if not already_stored(session, reading):
                    session.add(reading)
            status.last_success_at = utcnow()
            status.last_error = None
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            status.last_error = error

        session.add(status)
        session.add(
            FetchRun(
                source_id=source.source_id,
                started_at=started,
                finished_at=utcnow(),
                success=error is None,
                error=error,
            )
        )
        session.commit()
        return error is None


def create_scheduler(sources: Sequence[Source], engine: Engine) -> AsyncIOScheduler:
    """One interval job per registered source; each also fires once at startup."""
    scheduler = AsyncIOScheduler()
    for source in sources:
        scheduler.add_job(
            run_source,
            "interval",
            seconds=source.interval_seconds,
            args=(source, engine),
            id=source.source_id,
            next_run_time=datetime.now(UTC),
        )
    return scheduler
