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


def test_all_tables_round_trip(engine: Engine) -> None:
    now = utcnow()
    with Session(engine) as session:
        session.add(SourceStatus(source_id="s1", kind=SourceKind.ADVISORY, last_success_at=now))
        session.add(
            FetchRun(source_id="s1", started_at=now, finished_at=now, success=True, error=None)
        )
        session.add(RawFetch(source_id="s1", fetched_at=now, http_status=200, payload="{}"))
        advisory = AvalancheAdvisory(
            source_id="s1",
            fetched_at=now,
            region="Queenstown",
            issued_at=now,
            danger_high_alpine=3,
            danger_alpine=2,
            danger_sub_alpine=-2,
        )
        advisory.problems = [
            AvalancheProblem(character="Wind Slab", priority_level=1, aspects_alpine="N,NE")
        ]
        session.add(advisory)
        session.commit()

    with Session(engine) as session:
        status = session.exec(select(SourceStatus)).one()
        assert status.kind == SourceKind.ADVISORY
        assert status.last_success_at == now

        stored = session.exec(select(AvalancheAdvisory)).one()
        assert stored.danger_high_alpine == 3
        assert [p.character for p in stored.problems] == ["Wind Slab"]

        raw = session.exec(select(RawFetch)).one()
        assert raw.payload == "{}"

        run = session.exec(select(FetchRun)).one()
        assert run.success
