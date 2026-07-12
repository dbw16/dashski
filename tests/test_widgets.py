"""Widget endpoint tests: latest readings render, freshness/staleness surfaces."""

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session

from dashski.models import (
    ForecastReading,
    ObservationReading,
    SnowReport,
    SourceKind,
    SourceStatus,
    utcnow,
)


def _seed_status(engine: Engine, kind: SourceKind, *, error: str | None = None) -> None:
    with Session(engine) as session:
        session.add(
            SourceStatus(
                source_id=f"seed-{kind}",
                kind=kind,
                last_attempt_at=utcnow(),
                last_success_at=None if error else utcnow(),
                last_error=error,
            )
        )
        session.commit()


def test_forecast_widget_renders_readings(client: TestClient, engine: Engine) -> None:
    _seed_status(engine, SourceKind.FORECAST)
    with Session(engine) as session:
        session.add(
            ForecastReading(
                source_id="seed-forecast",
                fetched_at=utcnow(),
                location="The Remarkables",
                forecast_for=utcnow(),
                temp_high_c=2.0,
            )
        )
        session.commit()

    response = client.get("/api/widget/forecast")
    assert response.status_code == 200
    assert "The Remarkables" in response.text
    assert "updated just now" in response.text


def test_observation_widget_renders_readings(client: TestClient, engine: Engine) -> None:
    _seed_status(engine, SourceKind.OBSERVATION)
    with Session(engine) as session:
        session.add(
            ObservationReading(
                source_id="seed-observation",
                fetched_at=utcnow(),
                station="Coronet AWS",
                observed_at=utcnow(),
                temp_c=-3.0,
            )
        )
        session.commit()

    response = client.get("/api/widget/observation")
    assert response.status_code == 200
    assert "Coronet AWS" in response.text


def test_snow_report_widget_renders_readings(client: TestClient, engine: Engine) -> None:
    _seed_status(engine, SourceKind.SNOW_REPORT)
    with Session(engine) as session:
        session.add(
            SnowReport(
                source_id="seed-snow_report",
                fetched_at=utcnow(),
                ski_field="Coronet Peak",
                reported_at=utcnow(),
                base_depth_lower_cm=60.0,
                base_depth_upper_cm=85.0,
                season_snowfall_cm=120.0,
            )
        )
        session.commit()

    response = client.get("/api/widget/snow-report")
    assert response.status_code == 200
    assert "Coronet Peak" in response.text
    assert "60" in response.text
    assert "85" in response.text


def test_forecast_widget_shows_latest_reading_per_location(
    client: TestClient, engine: Engine
) -> None:
    _seed_status(engine, SourceKind.FORECAST)
    now = utcnow()
    with Session(engine) as session:
        session.add(
            ForecastReading(
                source_id="seed-forecast",
                fetched_at=now - timedelta(hours=1),
                location="The Remarkables",
                forecast_for=now,
                temp_high_c=1.0,
            )
        )
        session.add(
            ForecastReading(
                source_id="seed-forecast",
                fetched_at=now,
                location="The Remarkables",
                forecast_for=now,
                temp_high_c=2.0,
            )
        )
        session.commit()

    response = client.get("/api/widget/forecast")
    assert response.text.count("The Remarkables") == 1
    assert "2.0" in response.text


def test_observation_widget_shows_latest_reading_per_station(
    client: TestClient, engine: Engine
) -> None:
    _seed_status(engine, SourceKind.OBSERVATION)
    now = utcnow()
    with Session(engine) as session:
        session.add(
            ObservationReading(
                source_id="seed-observation",
                fetched_at=now - timedelta(hours=1),
                station="Coronet AWS",
                observed_at=now,
                temp_c=-5.0,
            )
        )
        session.add(
            ObservationReading(
                source_id="seed-observation",
                fetched_at=now,
                station="Coronet AWS",
                observed_at=now,
                temp_c=-3.0,
            )
        )
        session.commit()

    response = client.get("/api/widget/observation")
    assert response.text.count("Coronet AWS") == 1
    assert "-3.0" in response.text


def test_snow_report_widget_shows_each_field_once(client: TestClient, engine: Engine) -> None:
    _seed_status(engine, SourceKind.SNOW_REPORT)
    now = utcnow()
    with Session(engine) as session:
        for hours_ago, season_snowfall in ((2, 100.0), (1, 110.0), (0, 120.0)):
            session.add(
                SnowReport(
                    source_id="seed-snow_report",
                    fetched_at=now - timedelta(hours=hours_ago),
                    ski_field="Coronet Peak",
                    reported_at=now - timedelta(hours=hours_ago),
                    season_snowfall_cm=season_snowfall,
                )
            )
        session.commit()

    response = client.get("/api/widget/snow-report")
    assert response.text.count("Coronet Peak") == 1
    assert "120" in response.text  # most recently fetched row wins
    assert "100" not in response.text


def test_snow_report_widget_shows_direct_24h_without_calculated_marker(
    client: TestClient, engine: Engine
) -> None:
    _seed_status(engine, SourceKind.SNOW_REPORT)
    with Session(engine) as session:
        session.add(
            SnowReport(
                source_id="seed-snow_report",
                fetched_at=utcnow(),
                ski_field="Cardrona",
                reported_at=utcnow(),
                new_snow_24h_cm=8.0,
            )
        )
        session.commit()

    response = client.get("/api/widget/snow-report")
    assert "8.0" in response.text
    assert "8.0*" not in response.text
    assert "estimated from the 7-day trend" not in response.text


def test_snow_report_widget_calculates_24h_from_7d_trend(
    client: TestClient, engine: Engine
) -> None:
    _seed_status(engine, SourceKind.SNOW_REPORT)
    now = utcnow()
    with Session(engine) as session:
        session.add(
            SnowReport(
                source_id="seed-snow_report",
                fetched_at=now - timedelta(hours=24),
                ski_field="Treble Cone",
                reported_at=now - timedelta(hours=24),
                new_snow_7d_cm=10.0,
            )
        )
        session.add(
            SnowReport(
                source_id="seed-snow_report",
                fetched_at=now,
                ski_field="Treble Cone",
                reported_at=now,
                new_snow_7d_cm=15.0,
            )
        )
        session.commit()

    response = client.get("/api/widget/snow-report")
    assert "5.0*" in response.text
    assert "estimated from the 7-day trend" in response.text


def test_snow_report_widget_skips_24h_calc_when_prior_report_too_old(
    client: TestClient, engine: Engine
) -> None:
    _seed_status(engine, SourceKind.SNOW_REPORT)
    now = utcnow()
    with Session(engine) as session:
        session.add(
            SnowReport(
                source_id="seed-snow_report",
                fetched_at=now - timedelta(days=3),
                ski_field="Mt Hutt",
                reported_at=now - timedelta(days=3),
                new_snow_7d_cm=10.0,
            )
        )
        session.add(
            SnowReport(
                source_id="seed-snow_report",
                fetched_at=now,
                ski_field="Mt Hutt",
                reported_at=now,
                new_snow_7d_cm=15.0,
            )
        )
        session.commit()

    response = client.get("/api/widget/snow-report")
    assert "estimated from the 7-day trend" not in response.text


def test_snow_report_widget_clamps_negative_24h_calc_to_zero(
    client: TestClient, engine: Engine
) -> None:
    _seed_status(engine, SourceKind.SNOW_REPORT)
    now = utcnow()
    with Session(engine) as session:
        session.add(
            SnowReport(
                source_id="seed-snow_report",
                fetched_at=now - timedelta(hours=24),
                ski_field="Broken River",
                reported_at=now - timedelta(hours=24),
                new_snow_7d_cm=40.0,
            )
        )
        session.add(
            SnowReport(
                source_id="seed-snow_report",
                fetched_at=now,
                ski_field="Broken River",
                reported_at=now,
                new_snow_7d_cm=10.0,
            )
        )
        session.commit()

    response = client.get("/api/widget/snow-report")
    assert "0.0*" in response.text


def test_widget_with_no_data_shows_empty_state(client: TestClient) -> None:
    response = client.get("/api/widget/forecast")
    assert response.status_code == 200
    assert "No forecast data yet" in response.text
    assert "no data yet" in response.text


def test_widget_surfaces_failed_fetch_as_stale(client: TestClient, engine: Engine) -> None:
    _seed_status(engine, SourceKind.FORECAST, error="RuntimeError: connection refused")

    response = client.get("/api/widget/forecast")
    assert response.status_code == 200
    assert "last fetch failed" in response.text
    assert "status-dot-warn" in response.text


def test_dashboard_page_includes_all_widgets(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    for url in ("/api/widget/forecast", "/api/widget/observation", "/api/widget/snow-report"):
        assert f'hx-get="{url}"' in response.text
