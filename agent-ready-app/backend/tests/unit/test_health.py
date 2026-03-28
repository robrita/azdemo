"""Health endpoint tests."""

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    """GET /health returns ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_live(client: TestClient) -> None:
    """GET /health/live returns ok."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_ready(client: TestClient) -> None:
    """GET /health/ready returns ok when Cosmos is reachable."""
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
