from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.infrastructure.database import Base, get_db
from app.main import create_app
from app.modules.charging.domain.facility import Facility, FacilityType
from app.modules.charging.domain.station import ChargingStation, ConnectorStatus, ConnectorType
from app.modules.charging.infrastructure.charging_session_model import ChargingSessionModel
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.reservation_model import ReservationModel
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from app.modules.identity.application.security import create_access_token, hash_password
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from app.modules.simulation.domain import SimulationRun
from app.modules.simulation.infrastructure import (
    SimulationEventReceiptModel,
    SimulationRunModel,
    SimulationRunRepository,
)
from app.modules.simulation.security import issue_run_credential
from app.modules.telemetry.infrastructure import TelemetrySampleModel
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def simulated_client(
    monkeypatch: MonkeyPatch,
) -> Iterator[tuple[TestClient, sessionmaker[Session], User, UUID, UUID, str, datetime]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    logical_start = datetime(2026, 1, 1, tzinfo=UTC)
    with sessions() as db:
        driver = SqlAlchemyUserRepository(db).add(
            User.create(
                email="simulated-driver@example.com",
                display_name="Simulated Driver",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.EV_DRIVER],
                facility_ids=[],
            )
        )
        facility = SqlAlchemyFacilityRepository(db).add(
            Facility.create(
                name="Dedicated Simulation Facility",
                facility_type=FacilityType.UNIVERSITY,
                timezone="UTC",
                country="Brazil",
                city="Juiz de Fora",
                address="Synthetic Campus",
            )
        )
        station = SqlAlchemyChargingStationRepository(db).add(
            ChargingStation.create(
                facility_id=facility.id,
                name="Simulation Station",
                description=None,
                serial_number="SIM-OPS-1",
                manufacturer=None,
                model=None,
                maximum_power_kw=22,
                connectors=[(ConnectorType.TYPE2, 22, ConnectorStatus.AVAILABLE)],
            )
        )
        plaintext, credential_hash = issue_run_credential()
        draft = SimulationRun.create(
            logical_start_at=logical_start,
            logical_end_at=logical_start + timedelta(days=1),
            facility_ids=[facility.id],
            evdriver_ids=[driver.id],
            created_by=driver.id,
            now=datetime.now(UTC),
        )
        runs = SimulationRunRepository(db)
        runs.add(draft)
        run = runs.save(draft.start(credential_hash=credential_hash, now=datetime.now(UTC)))

    def override_get_db() -> Iterator[Session]:
        with sessions() as db:
            yield db

    monkeypatch.setattr("app.main.bootstrap_admin", lambda *_args: None)
    app = create_app(export_telemetry=False)
    app.dependency_overrides[get_db] = override_get_db
    jwt, _ = create_access_token(driver)
    with TestClient(app, headers={"Authorization": f"Bearer {jwt}"}) as client:
        yield (
            client,
            sessions,
            driver,
            station.connectors[0].id,
            run.id,
            plaintext,
            logical_start,
        )
    Base.metadata.drop_all(engine)
    engine.dispose()


def headers(run_id: UUID, token: str, simulated_at: datetime, event_id: UUID) -> dict[str, str]:
    return {
        "X-Simulation-Run-Id": str(run_id),
        "X-Simulation-Token": token,
        "X-Simulated-At": simulated_at.isoformat(),
        "X-Simulation-Event-Id": str(event_id),
    }


def test_simulated_reservation_is_atomic_idempotent_and_monotonic(
    simulated_client: tuple[TestClient, sessionmaker[Session], User, UUID, UUID, str, datetime],
) -> None:
    client, sessions, _driver, connector_id, run_id, token, start = simulated_client
    vehicle = client.post("/vehicles", json={"display_name": "Simulated EV"}).json()
    event_id = uuid4()
    accepted_at = start + timedelta(minutes=10)
    payload = {
        "vehicle_id": vehicle["id"],
        "connector_id": str(connector_id),
        "start_at": (start + timedelta(hours=1)).isoformat(),
        "end_at": (start + timedelta(hours=2)).isoformat(),
    }
    request_headers = headers(run_id, token, accepted_at, event_id)
    created = client.post("/reservations", json=payload, headers=request_headers)
    assert created.status_code == 201
    retry = client.post("/reservations", json=payload, headers=request_headers)
    assert retry.status_code == 201
    assert retry.json() == created.json()
    conflict = client.post(
        "/reservations",
        json=payload | {"end_at": (start + timedelta(hours=3)).isoformat()},
        headers=request_headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "SIMULATION_EVENT_IDEMPOTENCY_CONFLICT"
    stale = client.post(
        f"/reservations/{created.json()['reservation']['id']}/cancel",
        headers=headers(run_id, token, start + timedelta(minutes=5), uuid4()),
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "SIMULATION_TIME_REGRESSION"

    with sessions() as db:
        row = db.get(ReservationModel, UUID(created.json()["reservation"]["id"]))
        run = db.get(SimulationRunModel, run_id)
        assert row is not None and row.simulation_run_id == run_id
        assert run is not None and run.last_accepted_simulated_at == accepted_at.replace(
            tzinfo=None
        )
        assert db.scalar(select(func.count()).select_from(SimulationEventReceiptModel)) == 1


def test_partial_or_unsupported_simulation_context_is_rejected(
    simulated_client: tuple[TestClient, sessionmaker[Session], User, UUID, UUID, str, datetime],
) -> None:
    client, _sessions, _driver, _connector_id, run_id, _token, _start = simulated_client
    partial = client.post("/reservations", json={}, headers={"X-Simulation-Run-Id": str(run_id)})
    assert partial.status_code == 400
    assert partial.json()["detail"]["code"] == "SIMULATION_CONTEXT_INCOMPLETE"
    unsupported = client.post("/vehicles", json={}, headers={"X-Simulation-Run-Id": str(run_id)})
    assert unsupported.status_code == 400
    assert unsupported.json()["detail"]["code"] == "SIMULATION_CONTEXT_NOT_SUPPORTED"


def test_complete_simulated_flow_propagates_time_provenance_and_receipts(
    simulated_client: tuple[TestClient, sessionmaker[Session], User, UUID, UUID, str, datetime],
) -> None:
    client, sessions, _driver, connector_id, run_id, token, start = simulated_client
    vehicle = client.post("/vehicles", json={"display_name": "Flow EV"}).json()
    reservation_start = start + timedelta(hours=1)
    reservation_end = start + timedelta(hours=2)
    created = client.post(
        "/reservations",
        json={
            "vehicle_id": vehicle["id"],
            "connector_id": str(connector_id),
            "start_at": reservation_start.isoformat(),
            "end_at": reservation_end.isoformat(),
        },
        headers=headers(run_id, token, start, uuid4()),
    )
    assert created.status_code == 201
    reservation_id = created.json()["reservation"]["id"]
    activated = client.post(
        f"/reservations/{reservation_id}/charging-session",
        headers=headers(run_id, token, reservation_start, uuid4()),
    )
    assert activated.status_code == 201
    session_id = activated.json()["id"]
    telemetry_time = reservation_start + timedelta(minutes=30)
    telemetry = client.post(
        f"/charging-sessions/{session_id}/telemetry/batch",
        json={
            "samples": [
                {
                    "sample_id": "flow-1",
                    "source": "SIMULATOR",
                    "recorded_at": telemetry_time.isoformat(),
                    "power_kw": 11,
                }
            ]
        },
        headers=headers(run_id, token, telemetry_time, uuid4()),
    )
    assert telemetry.status_code == 201
    assert (
        datetime.fromisoformat(telemetry.json()[0]["received_at"].replace("Z", "+00:00"))
        == telemetry_time
    )
    completed = client.post(
        f"/charging-sessions/{session_id}/complete",
        headers=headers(run_id, token, reservation_end, uuid4()),
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "COMPLETED"

    with sessions() as db:
        session = db.get(ChargingSessionModel, UUID(session_id))
        sample = db.scalar(
            select(TelemetrySampleModel).where(TelemetrySampleModel.session_id == UUID(session_id))
        )
        run = db.get(SimulationRunModel, run_id)
        assert session is not None and session.simulation_run_id == run_id
        assert sample is not None and sample.received_at == telemetry_time.replace(tzinfo=None)
        assert run is not None and run.last_accepted_simulated_at == reservation_end.replace(
            tzinfo=None
        )
        assert db.scalar(select(func.count()).select_from(SimulationEventReceiptModel)) == 4
