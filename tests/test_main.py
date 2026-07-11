from fastapi.testclient import TestClient

from dashski.main import app

client = TestClient(app)


def test_dashboard_renders() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Dashski" in response.text
    assert "Online" in response.text


def test_time_fragment() -> None:
    response = client.get("/api/time")
    assert response.status_code == 200
    assert 'id="server-time"' in response.text


def test_ping_increments_count() -> None:
    first = client.post("/api/ping")
    second = client.post("/api/ping")
    assert first.status_code == 200
    assert second.status_code == 200
    assert 'id="ping-count"' in second.text
