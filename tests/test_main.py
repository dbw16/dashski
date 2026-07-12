from fastapi.testclient import TestClient

from dashski.main import app

client = TestClient(app)


def test_dashboard_renders() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Dashski" in response.text
