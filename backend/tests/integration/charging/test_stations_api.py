from collections.abc import Iterator

import pytest
from app.infrastructure.database import Base, get_db
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from tests.integration.charging.test_facilities_api import facility_payload


@pytest.fixture
def client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(engine)


def station_payload(serial: str = "SN-1") -> dict[str, object]:
    return {
        "name": "Station A",
        "description": "North lot",
        "serial_number": serial,
        "manufacturer": "SCEP",
        "model": "SC-50",
        "maximum_power_kw": 50.0,
        "status": "Active",
        "connectors": [{"connector_type": "CCS2", "maximum_power_kw": 50.0, "status": "Available"}],
    }


def create_facility(client: TestClient, *, status: str = "Active") -> str:
    payload = facility_payload(f"Facility {status}")
    payload["status"] = status
    response = client.post("/facilities", json=payload)
    assert response.status_code == 201
    return str(response.json()["id"])


def test_station_api_lifecycle(client: TestClient) -> None:
    facility_id = create_facility(client)
    create = client.post(f"/facilities/{facility_id}/stations", json=station_payload())
    assert create.status_code == 201
    station = create.json()
    assert station["connectors"][0]["connector_type"] == "CCS2"

    assert client.get(f"/facilities/{facility_id}/stations").json()[0]["id"] == station["id"]
    assert client.get(f"/stations/{station['id']}").json()["connectors"][0]["status"] == "Available"

    patch = client.patch(
        f"/stations/{station['id']}",
        json={"name": "Station B", "description": None, "status": "UnderMaintenance"},
    )
    assert patch.status_code == 200
    assert patch.json()["serial_number"] == "SN-1"

    bad_patch = client.patch(
        f"/stations/{station['id']}",
        json={
            "name": "Station B",
            "description": None,
            "status": "Active",
            "serial_number": "changed",
        },
    )
    assert bad_patch.status_code == 422

    add = client.post(
        f"/stations/{station['id']}/connectors",
        json={"connector_type": "NACS", "maximum_power_kw": 25.0, "status": "Available"},
    )
    assert add.status_code == 201
    connector_id = add.json()["id"]
    status_response = client.patch(
        f"/connectors/{connector_id}/status", json={"status": "OutOfService"}
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "OutOfService"


def test_station_api_validation_and_contract(client: TestClient) -> None:
    facility_id = create_facility(client)
    assert (
        client.post(f"/facilities/{facility_id}/stations", json=station_payload()).status_code
        == 201
    )
    assert (
        client.post(f"/facilities/{facility_id}/stations", json=station_payload()).status_code
        == 409
    )
    no_connectors = station_payload("SN-2")
    no_connectors["connectors"] = []
    assert client.post(f"/facilities/{facility_id}/stations", json=no_connectors).status_code == 422
    bad_power = station_payload("SN-3")
    bad_power["maximum_power_kw"] = 0
    assert client.post(f"/facilities/{facility_id}/stations", json=bad_power).status_code == 422
    inactive_facility_id = create_facility(client, status="Inactive")
    assert (
        client.post(
            f"/facilities/{inactive_facility_id}/stations", json=station_payload("SN-4")
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/facilities/00000000-0000-0000-0000-000000000000/stations",
            json=station_payload("SN-5"),
        ).status_code
        == 404
    )

    schema = client.get("/openapi.json").json()["paths"]
    for path in (
        "/facilities/{facility_id}/stations",
        "/stations/{station_id}",
        "/stations/{station_id}/connectors",
        "/connectors/{connector_id}/status",
    ):
        assert path in schema
        assert "delete" not in schema[path]
