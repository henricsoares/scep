from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from app.infrastructure.database import Base, get_db
from app.main import create_app
from app.modules.charging.domain.facility import Facility, FacilityType
from app.modules.charging.domain.station import ChargingStation, ConnectorStatus, ConnectorType
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from app.modules.identity.application.security import create_access_token, hash_password
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def reservation_client(monkeypatch: MonkeyPatch) -> Iterator[tuple[TestClient, User, UUID]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Iterator[Session]:
        with sessions() as session:
            yield session

    monkeypatch.setattr("app.main.bootstrap_admin", lambda *_args: None)
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with sessions() as session:
        owner = SqlAlchemyUserRepository(session).add(
            User.create(
                email="driver@example.com",
                display_name="Driver",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.EV_DRIVER],
                facility_ids=[],
            )
        )
        facility = SqlAlchemyFacilityRepository(session).add(
            Facility.create(
                name="Reservation Facility",
                facility_type=FacilityType.UNIVERSITY,
                timezone="UTC",
                country="Brazil",
                city="Juiz de Fora",
                address="Campus",
            )
        )
        station = SqlAlchemyChargingStationRepository(session).add(
            ChargingStation.create(
                facility_id=facility.id,
                name="Station",
                description=None,
                serial_number="RES-API-1",
                manufacturer=None,
                model=None,
                maximum_power_kw=22,
                connectors=[(ConnectorType.TYPE2, 22, ConnectorStatus.AVAILABLE)],
            )
        )
        connector_id = station.connectors[0].id

    token, _ = create_access_token(owner)
    with TestClient(app, headers={"Authorization": f"Bearer {token}"}) as client:
        yield client, owner, connector_id
    Base.metadata.drop_all(engine)


def test_owned_vehicle_and_reservation_api_workflow(
    reservation_client: tuple[TestClient, User, UUID],
) -> None:
    client, owner, connector_id = reservation_client
    vehicle_create = client.post("/vehicles", json={"display_name": "Primary EV"})
    assert vehicle_create.status_code == 201
    vehicle = vehicle_create.json()
    assert vehicle["owner_id"] == str(owner.id)
    assert client.get("/vehicles").json()[0]["id"] == vehicle["id"]

    start = datetime.now(UTC) + timedelta(hours=3)
    end = start + timedelta(hours=1)
    created = client.post(
        "/reservations",
        json={
            "vehicle_id": vehicle["id"],
            "connector_id": str(connector_id),
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
        },
    )
    assert created.status_code == 201
    item = created.json()["reservation"]
    assert item["status"] == "CONFIRMED"
    assert created.json()["warnings"] == []
    assert client.get(f"/reservations/{item['id']}").status_code == 200

    conflict = client.post(
        "/reservations",
        json={
            "vehicle_id": vehicle["id"],
            "connector_id": str(connector_id),
            "start_at": (start + timedelta(minutes=30)).isoformat(),
            "end_at": (end + timedelta(minutes=30)).isoformat(),
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "CONNECTOR_RESERVATION_CONFLICT"

    rescheduled = client.patch(
        f"/reservations/{item['id']}",
        json={
            "start_at": (start + timedelta(hours=1)).isoformat(),
            "end_at": (end + timedelta(hours=1)).isoformat(),
        },
    )
    assert rescheduled.status_code == 200
    cancelled = client.post(f"/reservations/{item['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["reservation"]["status"] == "CANCELLED"

    inactive = client.patch(f"/vehicles/{vehicle['id']}", json={"status": "INACTIVE"})
    assert inactive.status_code == 200
    rejected = client.post(
        "/reservations",
        json={
            "vehicle_id": vehicle["id"],
            "connector_id": str(connector_id),
            "start_at": (start + timedelta(hours=4)).isoformat(),
            "end_at": (end + timedelta(hours=4)).isoformat(),
        },
    )
    assert rejected.status_code == 422


def test_openapi_contains_spec_006_routes(
    reservation_client: tuple[TestClient, User, UUID],
) -> None:
    client, _, _ = reservation_client
    paths = client.get("/openapi.json").json()["paths"]
    for path in (
        "/vehicles",
        "/vehicles/{vehicleId}",
        "/reservations",
        "/reservations/{reservationId}",
        "/reservations/{reservationId}/cancel",
        "/connectors/{connectorId}/reservations",
    ):
        assert path in paths
        assert "delete" not in paths[path]
