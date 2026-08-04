from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

import pytest
from app.infrastructure.database import Base, get_db
from app.modules.charging.infrastructure import FacilityModel
from app.modules.charging.infrastructure.charging_session_model import ChargingSessionModel
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.application.security import hash_password
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from app.modules.simulation.api import router
from app.modules.simulation.infrastructure import SimulationRunModel
from app.modules.simulation.security import verify_run_credential
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_ = ChargingSessionModel


@pytest.fixture
def simulation_client() -> Iterator[tuple[TestClient, sessionmaker[Session], User, User, str]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with sessions() as db:
        users = SqlAlchemyUserRepository(db)
        admin = users.add(
            User.create(
                email=f"admin-{uuid4()}@example.com",
                display_name="Simulation Admin",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.PLATFORM_ADMINISTRATOR],
                facility_ids=[],
            )
        )
        driver = users.add(
            User.create(
                email=f"driver-{uuid4()}@example.com",
                display_name="Simulation Driver",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.EV_DRIVER],
                facility_ids=[],
            )
        )
        facility_id = uuid4()
        db.add(
            FacilityModel(
                id=facility_id,
                name=f"Simulation Facility {facility_id}",
                facility_type="University",
                timezone="UTC",
                country="Brazil",
                city="Juiz de Fora",
                address="Campus",
                operating_hours=None,
                status="Active",
            )
        )
        db.commit()

    app = FastAPI()
    app.include_router(router)

    def override_db() -> Iterator[Session]:
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = lambda: admin
    client = TestClient(app)
    yield client, sessions, admin, driver, str(facility_id)
    client.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_administrator_creates_starts_reads_bootstrap_and_cancels_run(
    simulation_client: tuple[TestClient, sessionmaker[Session], User, User, str],
) -> None:
    client, sessions, admin, driver, facility_id = simulation_client
    logical_start = datetime(2026, 1, 1, tzinfo=UTC)
    created = client.post(
        "/simulation-runs",
        json={
            "logical_start_at": logical_start.isoformat(),
            "logical_end_at": (logical_start + timedelta(days=7)).isoformat(),
            "facility_ids": [facility_id],
            "evdriver_ids": [str(driver.id)],
            "external_scenario_id": "reference-week",
            "scenario_sha256": "a" * 64,
            "simulator_version": "1.0.0",
        },
    )
    assert created.status_code == 201
    run = created.json()
    assert run["status"] == "DRAFT"
    assert run["created_by"] == str(admin.id)
    assert "credential_hash" not in run
    run_id = run["id"]

    started = client.post(f"/simulation-runs/{run_id}/start")
    assert started.status_code == 200
    token = started.json()["simulation_token"]
    assert started.json()["simulation_run"]["status"] == "RUNNING"
    assert token
    with sessions() as db:
        stored = db.get(SimulationRunModel, UUID(run_id))
        assert stored is not None
        assert stored.credential_hash is not None
        assert token not in stored.credential_hash
        assert verify_run_credential(token, stored.credential_hash)

    read = client.get(f"/simulation-runs/{run_id}")
    assert read.status_code == 200
    assert "simulation_token" not in read.json()
    bootstrap = client.get(f"/simulation-runs/{run_id}/bootstrap")
    assert bootstrap.status_code == 200
    assert bootstrap.json()["authorized_facility_ids"] == [facility_id]
    assert bootstrap.json()["authorized_evdriver_ids"] == [str(driver.id)]
    assert "simulation_token" not in bootstrap.text
    assert "credential" not in bootstrap.text
    assert "seed" not in bootstrap.text

    cancelled = client.post(f"/simulation-runs/{run_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert client.post(f"/simulation-runs/{run_id}/start").status_code == 409


def test_only_draft_runs_may_be_updated_and_invalid_associations_are_rejected(
    simulation_client: tuple[TestClient, sessionmaker[Session], User, User, str],
) -> None:
    client, _sessions, _admin, driver, facility_id = simulation_client
    logical_start = datetime(2026, 1, 1, tzinfo=UTC)
    payload = {
        "logical_start_at": logical_start.isoformat(),
        "logical_end_at": (logical_start + timedelta(days=1)).isoformat(),
        "facility_ids": [facility_id],
        "evdriver_ids": [str(driver.id)],
    }
    created = client.post("/simulation-runs", json=payload)
    run_id = created.json()["id"]
    patched = client.patch(f"/simulation-runs/{run_id}", json={"external_scenario_version": "v2"})
    assert patched.status_code == 200
    assert patched.json()["external_scenario_version"] == "v2"
    assert client.post(f"/simulation-runs/{run_id}/start").status_code == 200
    assert client.patch(f"/simulation-runs/{run_id}", json={"facility_ids": []}).status_code == 409

    invalid = payload | {"facility_ids": [str(uuid4())]}
    rejected = client.post("/simulation-runs", json=invalid)
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "SIMULATION_RUN_INVALID"


def test_researcher_can_manage_runs_but_data_scientist_cannot(
    simulation_client: tuple[TestClient, sessionmaker[Session], User, User, str],
) -> None:
    client, _sessions, _admin, driver, facility_id = simulation_client
    researcher = User.create(
        email=f"researcher-{uuid4()}@example.com",
        display_name="Simulation Researcher",
        password_hash="hash",
        account_type=AccountType.HUMAN,
        status=AccountStatus.ACTIVE,
        roles=[HumanRole.RESEARCHER],
        facility_ids=[],
    )
    payload = {
        "logical_start_at": "2026-01-01T00:00:00Z",
        "logical_end_at": "2026-01-02T00:00:00Z",
        "facility_ids": [facility_id],
        "evdriver_ids": [str(driver.id)],
    }
    app = cast(FastAPI, client.app)
    app.dependency_overrides[current_user] = lambda: researcher
    created = client.post("/simulation-runs", json=payload)
    assert created.status_code == 201
    assert created.json()["created_by"] == str(researcher.id)

    data_scientist = replace(researcher, roles=(HumanRole.DATA_SCIENTIST,))
    app.dependency_overrides[current_user] = lambda: data_scientist
    assert client.get(f"/simulation-runs/{created.json()['id']}").status_code == 403
