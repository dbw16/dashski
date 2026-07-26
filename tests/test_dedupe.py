"""Tests for the one-off cleanup of pre-ADR-0016 duplicate rows."""

from datetime import datetime
from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import Session, create_engine, select

from dashski import db
from dashski.dedupe import backup, delete_advisories, redundant_advisories
from dashski.models import AvalancheAdvisory, AvalancheProblem

ISSUED = datetime(2026, 7, 25, 8, 30)


def _advisory(fetched_at: datetime, danger: int = 3, size: float = 2.0) -> AvalancheAdvisory:
    advisory = AvalancheAdvisory(
        source_id="nzaa",
        fetched_at=fetched_at,
        region="Queenstown",
        issued_at=ISSUED,
        danger_alpine=danger,
    )
    advisory.problems = [AvalancheProblem(character="Wind Slab", size=size)]
    return advisory


def _store(engine: Engine, *advisories: AvalancheAdvisory) -> None:
    with Session(engine) as session:
        for advisory in advisories:
            session.add(advisory)
        session.commit()


def _cleanup(engine: Engine) -> int:
    with Session(engine) as session:
        rows = redundant_advisories(session)
        delete_advisories(session, rows)
        return len(rows)


def test_identical_rows_collapse_to_the_earliest_fetch(engine: Engine) -> None:
    _store(
        engine,
        _advisory(datetime(2026, 7, 26, 2, 0)),
        _advisory(datetime(2026, 7, 26, 3, 0)),
        _advisory(datetime(2026, 7, 26, 4, 0)),
    )

    assert _cleanup(engine) == 2

    with Session(engine) as session:
        kept = session.exec(select(AvalancheAdvisory)).one()
        assert kept.fetched_at == datetime(2026, 7, 26, 2, 0)
        # The Snapshot that first showed this advisory is the one that survives.
        assert len(session.exec(select(AvalancheProblem)).all()) == 1


def test_changed_rows_are_kept(engine: Engine) -> None:
    _store(
        engine,
        _advisory(datetime(2026, 7, 26, 2, 0), danger=3),
        _advisory(datetime(2026, 7, 26, 3, 0), danger=3),
        _advisory(datetime(2026, 7, 26, 4, 0), danger=4),
    )

    assert _cleanup(engine) == 1

    with Session(engine) as session:
        stored = session.exec(select(AvalancheAdvisory)).all()
        assert sorted(a.danger_alpine or 0 for a in stored) == [3, 4]


def test_a_problem_only_change_is_kept(engine: Engine) -> None:
    _store(
        engine,
        _advisory(datetime(2026, 7, 26, 2, 0), size=2.0),
        _advisory(datetime(2026, 7, 26, 3, 0), size=3.0),
    )

    assert _cleanup(engine) == 0


def test_regions_are_deduped_independently(engine: Engine) -> None:
    wanaka = _advisory(datetime(2026, 7, 26, 3, 0))
    wanaka.region = "Wanaka"
    _store(engine, _advisory(datetime(2026, 7, 26, 2, 0)), wanaka)

    assert _cleanup(engine) == 0


def test_reporting_alone_deletes_nothing(engine: Engine) -> None:
    _store(engine, _advisory(datetime(2026, 7, 26, 2, 0)), _advisory(datetime(2026, 7, 26, 3, 0)))

    with Session(engine) as session:
        assert len(redundant_advisories(session)) == 1

    with Session(engine) as session:
        assert len(session.exec(select(AvalancheAdvisory)).all()) == 2


def test_backup_keeps_the_rows_the_cleanup_deletes(tmp_path: Path) -> None:
    file_engine = create_engine(f"sqlite:///{tmp_path / 'dashski.db'}")
    db.init_db(file_engine)
    _store(
        file_engine, _advisory(datetime(2026, 7, 26, 2, 0)), _advisory(datetime(2026, 7, 26, 3, 0))
    )

    backup_path = backup(file_engine)
    with Session(file_engine) as session:
        delete_advisories(session, redundant_advisories(session))
        assert len(session.exec(select(AvalancheAdvisory)).all()) == 1

    with Session(create_engine(f"sqlite:///{backup_path}")) as session:
        assert len(session.exec(select(AvalancheAdvisory)).all()) == 2
