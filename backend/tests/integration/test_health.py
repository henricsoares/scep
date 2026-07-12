from app.main import create_app
from fastapi.testclient import TestClient


def test_health_endpoint() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-request-id"]


def test_health_endpoint_reuses_only_valid_request_id() -> None:
    with TestClient(create_app()) as client:
        accepted = client.get("/health", headers={"X-Request-ID": "caller-request-123"})
        rejected = client.get("/health", headers={"X-Request-ID": "malformed request id"})
    assert accepted.headers["x-request-id"] == "caller-request-123"
    assert rejected.headers["x-request-id"] != "malformed request id"


def test_liveness_endpoint() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
