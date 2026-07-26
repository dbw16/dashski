"""Cross-cutting widget behaviour: freshness/staleness, page wiring, empty history.

Advisory rendering itself lives in test_advisory_widget.py.
"""

from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlmodel import Session

from dashski.models import SourceKind, SourceStatus, utcnow


def _seed_status(engine: Engine, *, error: str | None = None) -> None:
    with Session(engine) as session:
        session.add(
            SourceStatus(
                source_id="seed-advisory",
                kind=SourceKind.ADVISORY,
                last_attempt_at=utcnow(),
                last_success_at=None if error else utcnow(),
                last_error=error,
            )
        )
        session.commit()


def test_widget_with_no_data_shows_empty_state(client: TestClient) -> None:
    response = client.get("/api/widget/advisory")
    assert response.status_code == 200
    assert "No advisory data" in response.text
    assert "no data yet" in response.text


def test_widget_surfaces_failed_fetch_as_stale(client: TestClient, engine: Engine) -> None:
    _seed_status(engine, error="RuntimeError: connection refused")

    response = client.get("/api/widget/advisory")
    assert response.status_code == 200
    assert "last fetch failed" in response.text
    assert "status-dot-warn" in response.text


def test_dashboard_page_includes_all_widgets(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'hx-get="/api/widget/advisory"' in response.text
    assert 'hx-get="/api/snapshots"' in response.text


def test_snapshots_endpoint_empty_shows_no_history(client: TestClient) -> None:
    response = client.get("/api/snapshots")
    assert response.status_code == 200
    assert "No history yet" in response.text
