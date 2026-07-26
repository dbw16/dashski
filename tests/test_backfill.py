"""Tests for the historical backfill: frontier tracking, restartability, dedupe.

The network is faked throughout — `fetch_history` is the only seam that touches it.
"""

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlmodel import Session, select

from dashski import backfill
from dashski.models import AvalancheAdvisory, FetchRun, SourceStatus
from dashski.sources.nzaa_advisory import HISTORY_BEGINS, REGIONS, SOURCE_ID, Region

QUEENSTOWN = REGIONS[0]


def _advisory(region: str, issued_at: datetime, danger: int = 2) -> AvalancheAdvisory:
    """A backfilled advisory, snapshotted at its issue time as parse_history builds them."""
    return AvalancheAdvisory(
        source_id=SOURCE_ID,
        fetched_at=issued_at,
        region=region,
        issued_at=issued_at,
        danger_alpine=danger,
    )


class FakeHistory:
    """Stands in for the endpoint: answers with the latest advisory at or before a day."""

    def __init__(self, published: dict[date, int] | None = None) -> None:
        # One advisory per listed day, issued 19:00 NZ (07:00 UTC next day).
        self.published = published if published is not None else {}
        self.asked: list[tuple[str, date]] = []

    def __call__(self, region: Region, day: date) -> AvalancheAdvisory | None:
        self.asked.append((region.name, day))
        standing = [d for d in self.published if d <= day]
        if not standing:
            return None
        latest = max(standing)
        issued = datetime(latest.year, latest.month, latest.day, 7)
        return _advisory(region.name, issued, self.published[latest])


@pytest.fixture
def no_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backfill.time, "sleep", lambda _: None)


def _patch(monkeypatch: pytest.MonkeyPatch, fake: FakeHistory) -> None:
    monkeypatch.setattr(backfill, "fetch_history", fake)


def _stored(session: Session, region: str = "Queenstown") -> list[AvalancheAdvisory]:
    rows = session.exec(select(AvalancheAdvisory).where(AvalancheAdvisory.region == region)).all()
    return sorted(rows, key=lambda r: r.issued_at)


def test_frontier_is_today_when_region_has_nothing(engine: Engine) -> None:
    with Session(engine) as session:
        assert backfill.frontier(session, QUEENSTOWN) == datetime.now(backfill.NZ).date()


def test_frontier_is_the_oldest_stored_advisory_in_nz_days(engine: Engine) -> None:
    with Session(engine) as session:
        # 2025-08-14 19:00 NZ is 07:00 UTC on the 14th; the NZ day is what counts.
        session.add(_advisory("Queenstown", datetime(2025, 8, 14, 7)))
        session.add(_advisory("Queenstown", datetime(2025, 8, 20, 7)))
        session.commit()

        assert backfill.frontier(session, QUEENSTOWN) == date(2025, 8, 14)


def test_frontier_is_per_region(engine: Engine) -> None:
    """A region tracked from later has its own gap; a shared frontier would skip it."""
    with Session(engine) as session:
        session.add(_advisory("Queenstown", datetime(2025, 8, 1, 7)))
        session.add(_advisory("Wanaka", datetime(2025, 8, 20, 7)))
        session.commit()

        assert backfill.frontier(session, REGIONS[0]) == date(2025, 8, 1)
        assert backfill.frontier(session, REGIONS[1]) == date(2025, 8, 20)


def test_days_to_fetch_walks_backwards_excluding_the_frontier() -> None:
    days = list(backfill.days_to_fetch(date(2025, 8, 10), 3))

    assert days == [date(2025, 8, 9), date(2025, 8, 8), date(2025, 8, 7)]


def test_days_to_fetch_stops_at_the_start_of_records() -> None:
    days = list(backfill.days_to_fetch(HISTORY_BEGINS + timedelta(days=2), 30))

    assert days == [HISTORY_BEGINS + timedelta(days=1), HISTORY_BEGINS]


def test_stores_one_row_per_publication_not_per_day(
    engine: Engine, no_delay: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An advisory that stood for three days comes back three times and stores once."""
    fake = FakeHistory({date(2025, 8, 5): 3})
    _patch(monkeypatch, fake)

    with Session(engine) as session:
        fetched, stored = backfill.backfill_region(
            session, QUEENSTOWN, date(2025, 8, 10), 4, delay=0, dry_run=False
        )

        assert (fetched, stored) == (4, 1)
        assert len(_stored(session)) == 1


def test_stores_each_distinct_advisory(
    engine: Engine, no_delay: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, FakeHistory({date(2025, 8, 7): 3, date(2025, 8, 8): 1}))

    with Session(engine) as session:
        _, stored = backfill.backfill_region(
            session, QUEENSTOWN, date(2025, 8, 10), 4, delay=0, dry_run=False
        )

        assert stored == 2
        assert [a.danger_alpine for a in _stored(session)] == [3, 1]


def test_stops_walking_once_records_run_out(
    engine: Engine, no_delay: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Earlier days can only be emptier, so the walk ends rather than burning requests."""
    fake = FakeHistory({date(2025, 8, 8): 2})
    _patch(monkeypatch, fake)

    with Session(engine) as session:
        fetched, _ = backfill.backfill_region(
            session, QUEENSTOWN, date(2025, 8, 10), 100, delay=0, dry_run=False
        )

        assert fetched == 3  # 9th, 8th, then the 7th answers with nothing
        assert fake.asked[-1] == ("Queenstown", date(2025, 8, 7))


def test_rerun_resumes_from_the_new_frontier(
    engine: Engine, no_delay: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The restart contract: a second run picks up where the first stopped."""
    published = {date(2025, 8, day): 2 for day in range(1, 11)}
    fake = FakeHistory(published)
    _patch(monkeypatch, fake)

    with Session(engine) as session:
        session.add(_advisory("Queenstown", datetime(2025, 8, 10, 7)))
        session.commit()

        backfill.backfill_region(
            session, QUEENSTOWN, backfill.frontier(session, QUEENSTOWN), 3, delay=0, dry_run=False
        )
        assert backfill.frontier(session, QUEENSTOWN) == date(2025, 8, 7)

        backfill.backfill_region(
            session, QUEENSTOWN, backfill.frontier(session, QUEENSTOWN), 3, delay=0, dry_run=False
        )

        assert backfill.frontier(session, QUEENSTOWN) == date(2025, 8, 4)
        assert len(_stored(session)) == 7  # the 10th, plus the 9th down to the 4th


def test_rerunning_the_same_range_stores_nothing_twice(
    engine: Engine, no_delay: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch(monkeypatch, FakeHistory({date(2025, 8, 7): 3, date(2025, 8, 8): 1}))

    with Session(engine) as session:
        args = (session, QUEENSTOWN, date(2025, 8, 10), 4)
        first = backfill.backfill_region(*args, delay=0, dry_run=False)
        second = backfill.backfill_region(*args, delay=0, dry_run=False)

        assert (first[1], second[1]) == (2, 0)


def test_dry_run_writes_nothing_and_does_not_double_count(
    engine: Engine, no_delay: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without commits the DB can't dedupe, so the run tracks what it has seen itself."""
    _patch(monkeypatch, FakeHistory({date(2025, 8, 5): 3}))

    with Session(engine) as session:
        _, stored = backfill.backfill_region(
            session, QUEENSTOWN, date(2025, 8, 10), 4, delay=0, dry_run=True
        )

        assert stored == 1
        assert _stored(session) == []


def test_creates_the_source_row_but_no_fetch_bookkeeping(engine: Engine) -> None:
    """A backfill is not a Fetch Run — it must not shift the staleness indicators."""
    with Session(engine) as session:
        backfill.ensure_source_row(session)

        status = session.get(SourceStatus, SOURCE_ID)
        assert status is not None
        assert status.last_attempt_at is None and status.last_success_at is None
        assert session.exec(select(FetchRun)).all() == []


def test_run_covers_every_region(
    engine: Engine, no_delay: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeHistory({date(2025, 8, 5): 3})
    _patch(monkeypatch, fake)

    backfill.run(engine, 2, delay=0, dry_run=False)

    assert {name for name, _ in fake.asked} == {region.name for region in REGIONS}
    with Session(engine) as session:
        assert len(session.exec(select(AvalancheAdvisory)).all()) == len(REGIONS)
