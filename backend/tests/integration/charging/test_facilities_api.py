from collections.abc import Iterator

import pytest
from app.infrastructure.database import Base, get_db
from app.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


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


def facility_payload(name: str = "North Campus") -> dict[str, object]:
    return {
        "name": name,
        "facility_type": "University",
        "timezone": "America/New_York",
        "country": "United States",
        "city": "New York",
        "address": "123 Main St",
        "latitude": 40.7128,
        "longitude": -74.006,
        "operating_hours": {"monday": {"opens": "08:00", "closes": "22:00"}},
        "status": "Active",
    }


def test_facilities_api_create_lookup_update_and_deactivate(client: TestClient) -> None:
    create_response = client.post("/facilities", json=facility_payload())
    assert create_response.status_code == 201
    facility = create_response.json()

    assert client.get("/facilities").json()[0]["id"] == facility["id"]
    assert client.get(f"/facilities/{facility['id']}").json()["name"] == "North Campus"

    update_payload = facility_payload("South Campus")
    update_payload["status"] = "Inactive"
    update_response = client.put(f"/facilities/{facility['id']}", json=update_payload)
    assert update_response.status_code == 200
    assert update_response.json()["name"] == "South Campus"

    retrieved = client.get(f"/facilities/{facility['id']}")
    assert retrieved.status_code == 200
    assert retrieved.json()["status"] == "Inactive"


def test_facilities_api_validation_failures(client: TestClient) -> None:
    payload = facility_payload("")
    response = client.post("/facilities", json=payload)
    assert response.status_code == 422

    payload = facility_payload("Bad Timezone")
    payload["timezone"] = "Invalid/Zone"
    response = client.post("/facilities", json=payload)
    assert response.status_code == 422


def test_facilities_api_rejects_duplicate_names(client: TestClient) -> None:
    assert client.post("/facilities", json=facility_payload()).status_code == 201
    response = client.post("/facilities", json=facility_payload())
    assert response.status_code == 409


def test_facilities_openapi_documents_endpoints(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/facilities" in schema["paths"]
    assert "/facilities/{facilityId}" in schema["paths"]
