from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.modules.identity.domain.user import User
from fastapi.testclient import TestClient

from ..charging.test_reservations_api import reservation_client as _reservation_client  # noqa: F401


@pytest.fixture
def telemetry_client(request: pytest.FixtureRequest) -> tuple[TestClient, User, UUID]:
    return request.getfixturevalue("_reservation_client")  # type: ignore[no-any-return]


def active_session(client: TestClient, connector_id: UUID) -> dict[str, object]:
    vehicle = client.post("/vehicles", json={"display_name": "Telemetry EV"})
    start = datetime.now(UTC) + timedelta(seconds=5)
    reservation = client.post(
        "/reservations",
        json={
            "vehicle_id": vehicle.json()["id"],
            "connector_id": str(connector_id),
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
        },
    )
    activated = client.post(
        f"/reservations/{reservation.json()['reservation']['id']}/charging-session"
    )
    assert activated.status_code == 201
    return activated.json()  # type: ignore[no-any-return]


def payload(sample_id: str, recorded_at: str, power: float = 7.2) -> dict[str, object]:
    return {
        "sample_id": sample_id,
        "source": "SIMULATOR",
        "recorded_at": recorded_at,
        "power_kw": power,
    }


def test_single_idempotency_retrieval_filters_and_contract(
    telemetry_client: tuple[TestClient, User, UUID],
) -> None:
    client, _, connector_id = telemetry_client
    charging_session = active_session(client, connector_id)
    session_id = charging_session["id"]
    body = payload("single-1", str(charging_session["started_at"]))

    created = client.post(f"/charging-sessions/{session_id}/telemetry", json=body)
    assert created.status_code == 201
    retry = client.post(f"/charging-sessions/{session_id}/telemetry", json=body)
    assert retry.status_code == 200
    assert retry.json() == created.json()
    conflict = client.post(
        f"/charging-sessions/{session_id}/telemetry", json=body | {"power_kw": 8.0}
    )
    assert conflict.status_code == 409
    assert client.get(f"/telemetry/{created.json()['id']}").json() == created.json()
    listed = client.get(
        f"/charging-sessions/{session_id}/telemetry", params={"source": "SIMULATOR"}
    )
    assert listed.json() == [created.json()]


def test_batch_is_deterministic_atomic_and_reports_creation_semantics(
    telemetry_client: tuple[TestClient, User, UUID],
) -> None:
    client, _, connector_id = telemetry_client
    charging_session = active_session(client, connector_id)
    session_id = charging_session["id"]
    recorded = str(charging_session["started_at"])
    first = payload("first", recorded)
    second = payload("second", recorded, 11.0)

    created = client.post(
        f"/charging-sessions/{session_id}/telemetry/batch",
        json={"samples": [first, first, second]},
    )
    assert created.status_code == 201
    assert [item["sample_id"] for item in created.json()] == ["first", "second"]
    assert (
        client.post(
            f"/charging-sessions/{session_id}/telemetry/batch",
            json={"samples": [first, second]},
        ).status_code
        == 200
    )

    conflict = client.post(
        f"/charging-sessions/{session_id}/telemetry/batch",
        json={"samples": [payload("third", recorded), first | {"power_kw": 99}]},
    )
    assert conflict.status_code == 409
    listed = client.get(f"/charging-sessions/{session_id}/telemetry").json()
    assert [item["sample_id"] for item in listed] == ["first", "second"]


def test_temporal_measurement_authentication_and_openapi(
    telemetry_client: tuple[TestClient, User, UUID],
) -> None:
    client, _, connector_id = telemetry_client
    charging_session = active_session(client, connector_id)
    session_id = charging_session["id"]
    too_early = datetime.fromisoformat(str(charging_session["started_at"])) - timedelta(seconds=1)
    assert (
        client.post(
            f"/charging-sessions/{session_id}/telemetry",
            json=payload("early", too_early.isoformat()),
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/charging-sessions/{session_id}/telemetry",
            json={
                "sample_id": "empty",
                "source": "API_CLIENT",
                "recorded_at": charging_session["started_at"],
            },
        ).status_code
        == 422
    )

    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/charging-sessions/{sessionId}/telemetry",
        "/charging-sessions/{sessionId}/telemetry/batch",
        "/telemetry/{telemetryId}",
    ):
        assert path in paths
        assert "delete" not in paths[path]
        for operation in paths[path].values():
            assert operation["security"] == [{"HTTPBearer": []}]
