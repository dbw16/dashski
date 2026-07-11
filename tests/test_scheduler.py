"""Tests for the generic fetch framework, using fake sources — no network, no real adapters."""

from collections.abc import Sequence
from typing import override

from sqlalchemy import Engine
from sqlmodel import Session, select

from dashski.models import (
    FetchRun,
    ForecastReading,
    RawFetch,
    SourceKind,
    SourceStatus,
    utcnow,
)
from dashski.scheduler import create_scheduler, run_source
from dashski.sources.base import RawPayload


class FakeForecastSource:
    source_id = "fake-forecast"
    kind = SourceKind.FORECAST
    interval_seconds = 60

    def fetch(self) -> RawPayload:
        return RawPayload(text='{"high": 3}', http_status=200)

    def parse(self, raw: RawPayload) -> Sequence[ForecastReading]:
        return [
            ForecastReading(
                source_id=self.source_id,
                fetched_at=utcnow(),
                location="Fake Peak",
                forecast_for=utcnow(),
                temp_high_c=3.0,
            )
        ]


class FailingFetchSource(FakeForecastSource):
    source_id = "failing-fetch"

    @override
    def fetch(self) -> RawPayload:
        raise RuntimeError("connection refused")


class FailingParseSource(FakeForecastSource):
    source_id = "failing-parse"

    @override
    def parse(self, raw: RawPayload) -> Sequence[ForecastReading]:
        raise ValueError("page layout changed")


def test_run_source_stores_readings_raw_and_success(engine: Engine) -> None:
    run_source(FakeForecastSource(), engine)

    with Session(engine) as session:
        reading = session.exec(select(ForecastReading)).one()
        assert reading.location == "Fake Peak"

        raw = session.exec(select(RawFetch)).one()
        assert raw.payload == '{"high": 3}'
        assert raw.http_status == 200

        status = session.exec(select(SourceStatus)).one()
        assert status.last_success_at is not None
        assert status.last_error is None

        run = session.exec(select(FetchRun)).one()
        assert run.success


def test_fetch_failure_is_recorded_not_raised(engine: Engine) -> None:
    run_source(FailingFetchSource(), engine)

    with Session(engine) as session:
        status = session.exec(select(SourceStatus)).one()
        assert status.last_error == "RuntimeError: connection refused"
        assert status.last_success_at is None

        run = session.exec(select(FetchRun)).one()
        assert not run.success
        assert session.exec(select(ForecastReading)).all() == []


def test_parse_failure_still_keeps_raw_payload(engine: Engine) -> None:
    run_source(FailingParseSource(), engine)

    with Session(engine) as session:
        raw = session.exec(select(RawFetch)).one()
        assert raw.payload == '{"high": 3}'

        status = session.exec(select(SourceStatus)).one()
        assert status.last_error == "ValueError: page layout changed"
        assert session.exec(select(ForecastReading)).all() == []


def test_raw_fetch_is_overwritten_not_appended(engine: Engine) -> None:
    source = FakeForecastSource()
    run_source(source, engine)
    run_source(source, engine)

    with Session(engine) as session:
        assert len(session.exec(select(RawFetch)).all()) == 1
        assert len(session.exec(select(FetchRun)).all()) == 2


def test_create_scheduler_registers_one_job_per_source(engine: Engine) -> None:
    sources = [FakeForecastSource(), FailingFetchSource()]
    scheduler = create_scheduler(sources, engine)
    jobs = {job.id for job in scheduler.get_jobs()}
    assert jobs == {"fake-forecast", "failing-fetch"}
