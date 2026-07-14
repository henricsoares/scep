from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.modules.identity.domain.user import User
from fastapi.testclient import TestClient

from .test_reservations_api import reservation_client as _reservation_client  # noqa: F401


@pytest.fixture
def session_client(request: pytest.FixtureRequest) -> tuple[TestClient, User, UUID]:
    return request.getfixturevalue("_reservation_client")  # type: ignore[no-any-return]


def _create_reservation(client: TestClient, connector_id: UUID) -> tuple[str, str]:
    vehicle = client.post("/vehicles", json={"display_name": "Session EV"})
    assert vehicle.status_code == 201
    start = datetime.now(UTC) + timedelta(seconds=10)
    reservation = client.post(
        "/reservations",
        json={
            "vehicle_id": vehicle.json()["id"],
            "connector_id": str(connector_id),
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
        },
    )
    assert reservation.status_code == 201
    return vehicle.json()["id"], reservation.json()["reservation"]["id"]


def test_activate_list_retrieve_complete_workflow(
    session_client: tuple[TestClient, User, UUID],
) -> None:
    client, owner, connector_id = session_client
    vehicle_id, reservation_id = _create_reservation(client, connector_id)

    activated = client.post(f"/reservations/{reservation_id}/charging-session")
    assert activated.status_code == 201
    item = activated.json()
    assert item["reservation_id"] == reservation_id
    assert item["owner_id"] == str(owner.id)
    assert item["vehicle_id"] == vehicle_id
    assert item["connector_id"] == str(connector_id)
    assert item["status"] == "ACTIVE"
    assert item["ended_at"] is None

    duplicate = client.post(f"/reservations/{reservation_id}/charging-session")
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "RESERVATION_SESSION_CONFLICT"
    assert client.get("/charging-sessions").json()[0]["id"] == item["id"]
    assert client.get(f"/charging-sessions/{item['id']}").status_code == 200
    assert client.get(f"/connectors/{connector_id}/charging-sessions").json()[0]["id"] == item["id"]
    assert client.get(f"/vehicles/{vehicle_id}/charging-sessions").json()[0]["id"] == item["id"]

    completed = client.post(f"/charging-sessions/{item['id']}/complete")
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"
    assert completed.json()["ended_at"] is not None
    assert client.post(f"/charging-sessions/{item['id']}/complete").status_code == 422
    reservation = client.get(f"/reservations/{reservation_id}")
    assert reservation.json()["status"] == "COMPLETED"


def test_charging_session_openapi_routes(
    session_client: tuple[TestClient, User, UUID],
) -> None:
    client, _, _ = session_client
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/reservations/{reservationId}/charging-session",
        "/charging-sessions",
        "/charging-sessions/{sessionId}",
        "/charging-sessions/{sessionId}/complete",
        "/connectors/{connectorId}/charging-sessions",
        "/vehicles/{vehicleId}/charging-sessions",
    ):
        assert path in paths
        assert "delete" not in paths[path]
