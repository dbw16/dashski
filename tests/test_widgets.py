"""Widget endpoint tests: latest readings render, freshness/staleness surfaces."""

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
                base_depth_cm=85.0,
                lifts_open=4,
                lifts_total=5,
            )
        )
        session.commit()

    response = client.get("/api/widget/snow-report")
    assert response.status_code == 200
    assert "Coronet Peak" in response.text
    assert "4/5" in response.text


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
