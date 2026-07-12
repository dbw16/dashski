"""Wires registered sources through APScheduler: fetch → store raw → parse → store readings.

Each source's run is isolated: failures are caught and recorded on SourceStatus/FetchRun
(feeding the dashboard's staleness indicators) and never crash the scheduler or block
other sources.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import Engine
from sqlmodel import Session

from dashski.models import FetchRun, RawFetch, SourceStatus, utcnow
from dashski.sources.base import Source


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
