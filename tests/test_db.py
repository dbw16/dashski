from sqlalchemy import Engine
from sqlmodel import Session, select

from dashski.models import (
    FetchRun,
    ForecastReading,
    ObservationReading,
    RawFetch,
    SnowReport,
    SourceKind,
    SourceStatus,
    utcnow,
)


def test_all_tables_round_trip(engine: Engine) -> None:
    now = utcnow()
    with Session(engine) as session:
        session.add(SourceStatus(source_id="s1", kind=SourceKind.FORECAST, last_success_at=now))
        session.add(
            FetchRun(source_id="s1", started_at=now, finished_at=now, success=True, error=None)
        )
        session.add(RawFetch(source_id="s1", fetched_at=now, http_status=200, payload="{}"))
        session.add(
            ForecastReading(
                source_id="s1",
                fetched_at=now,
                location="The Remarkables",
                forecast_for=now,
                temp_high_c=2.0,
            )
        )
        session.add(
            ObservationReading(
                source_id="s1", fetched_at=now, station="Coronet AWS", observed_at=now, temp_c=-1.5
            )
        )
        session.add(
            SnowReport(
                source_id="s1",
                fetched_at=now,
                ski_field="Coronet Peak",
                reported_at=now,
                base_depth_lower_cm=60.0,
                base_depth_upper_cm=85.0,
                season_snowfall_cm=120.0,
            )
        )
        session.commit()

    with Session(engine) as session:
        status = session.exec(select(SourceStatus)).one()
        assert status.kind == SourceKind.FORECAST
        assert status.last_success_at == now

        forecast = session.exec(select(ForecastReading)).one()
        assert forecast.location == "The Remarkables"
        assert forecast.temp_high_c == 2.0

        observation = session.exec(select(ObservationReading)).one()
        assert observation.temp_c == -1.5

        report = session.exec(select(SnowReport)).one()
        assert report.base_depth_upper_cm == 85.0

        raw = session.exec(select(RawFetch)).one()
        assert raw.payload == "{}"

        run = session.exec(select(FetchRun)).one()
        assert run.success
