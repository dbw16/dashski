"""Tests for the generic fetch framework, using fake sources — no network, no real adapters."""

from collections.abc import Sequence
from datetime import datetime
from typing import override

from sqlalchemy import Engine
from sqlmodel import Session, select

from dashski.models import (
    AvalancheAdvisory,
    AvalancheProblem,
    FetchRun,
    RawFetch,
    SourceKind,
    SourceStatus,
    utcnow,
)
from dashski.scheduler import create_scheduler, run_source
from dashski.sources.base import RawPayload


class FakeAdvisorySource:
    source_id = "fake-advisory"
    kind = SourceKind.ADVISORY
    interval_seconds = 60

    def fetch(self) -> RawPayload:
        return RawPayload(text='{"danger": 3}', http_status=200)

    def parse(self, raw: RawPayload) -> Sequence[AvalancheAdvisory]:
        return [
            AvalancheAdvisory(
                source_id=self.source_id,
                fetched_at=utcnow(),
                region="Fake Region",
                issued_at=utcnow(),
                danger_alpine=3,
            )
        ]


class StableAdvisorySource(FakeAdvisorySource):
    """Republishes one unchanging advisory, the off-season case dedupe exists for."""

    source_id = "stable-advisory"
    danger = 3
    problem_size = 2.0

    @override
    def parse(self, raw: RawPayload) -> Sequence[AvalancheAdvisory]:
        advisory = AvalancheAdvisory(
            source_id=self.source_id,
            fetched_at=utcnow(),
            region="Fake Region",
            issued_at=datetime(2026, 7, 25, 8, 30),
            danger_alpine=self.danger,
        )
        advisory.problems = [AvalancheProblem(character="Wind Slab", size=self.problem_size)]
        return [advisory]


class FailingFetchSource(FakeAdvisorySource):
    source_id = "failing-fetch"

    @override
    def fetch(self) -> RawPayload:
        raise RuntimeError("connection refused")


class FailingParseSource(FakeAdvisorySource):
    source_id = "failing-parse"

    @override
    def parse(self, raw: RawPayload) -> Sequence[AvalancheAdvisory]:
        raise ValueError("page layout changed")


def test_run_source_stores_readings_raw_and_success(engine: Engine) -> None:
    run_source(FakeAdvisorySource(), engine)

    with Session(engine) as session:
        reading = session.exec(select(AvalancheAdvisory)).one()
        assert reading.region == "Fake Region"

        raw = session.exec(select(RawFetch)).one()
        assert raw.payload == '{"danger": 3}'
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
        assert session.exec(select(AvalancheAdvisory)).all() == []


def test_parse_failure_still_keeps_raw_payload(engine: Engine) -> None:
    run_source(FailingParseSource(), engine)

    with Session(engine) as session:
        raw = session.exec(select(RawFetch)).one()
        assert raw.payload == '{"danger": 3}'

        status = session.exec(select(SourceStatus)).one()
        assert status.last_error == "ValueError: page layout changed"
        assert session.exec(select(AvalancheAdvisory)).all() == []


def test_raw_fetch_is_overwritten_not_appended(engine: Engine) -> None:
    source = FakeAdvisorySource()
    run_source(source, engine)
    run_source(source, engine)

    with Session(engine) as session:
        assert len(session.exec(select(RawFetch)).all()) == 1
        assert len(session.exec(select(FetchRun)).all()) == 2


def test_unchanged_advisory_is_not_stored_again(engine: Engine) -> None:
    source = StableAdvisorySource()
    run_source(source, engine)
    run_source(source, engine)

    with Session(engine) as session:
        assert len(session.exec(select(AvalancheAdvisory)).all()) == 1
        assert len(session.exec(select(AvalancheProblem)).all()) == 1
        assert len(session.exec(select(FetchRun)).all()) == 2


def test_changed_advisory_is_stored_as_a_new_row(engine: Engine) -> None:
    source = StableAdvisorySource()
    run_source(source, engine)
    source.danger = 4
    run_source(source, engine)

    with Session(engine) as session:
        stored = session.exec(select(AvalancheAdvisory)).all()
        assert sorted(a.danger_alpine or 0 for a in stored) == [3, 4]


def test_changed_problem_alone_is_stored_as_a_new_row(engine: Engine) -> None:
    source = StableAdvisorySource()
    run_source(source, engine)
    source.problem_size = 3.0
    run_source(source, engine)

    with Session(engine) as session:
        assert len(session.exec(select(AvalancheAdvisory)).all()) == 2


def test_create_scheduler_registers_one_job_per_source(engine: Engine) -> None:
    sources = [FakeAdvisorySource(), FailingFetchSource()]
    scheduler = create_scheduler(sources, engine)
    jobs = {job.id for job in scheduler.get_jobs()}
    assert jobs == {"fake-advisory", "failing-fetch"}
