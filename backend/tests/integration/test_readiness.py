from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.main import create_app


def test_readiness_endpoint(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.health.check_database_ready", lambda: True)
    client = TestClient(create_app())
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "connected"}
