from __future__ import annotations

import io
import json
import os
import zipfile
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from typing import Any
from uuid import UUID, uuid4

import pytest
from app.core.config import Settings, get_settings
from app.infrastructure.database import Base, get_db
from app.modules.analytics.application.models import AnalyticsQuery, Granularity
from app.modules.analytics.application.service import AnalyticsService
from app.modules.analytics.infrastructure.repository import AnalyticsRepository
from app.modules.charging.infrastructure.charging_session_model import ChargingSessionModel
from app.modules.charging.infrastructure.dataset_export_reader import ChargingDatasetReader
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.charging.infrastructure.reservation_model import ReservationModel, VehicleModel
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel
from app.modules.datasets.api import router
from app.modules.datasets.domain import (
    CreateExport,
    DatasetType,
    ExportFilters,
    ExportFormat,
    ExportProfile,
    ExportStatus,
    FailureCode,
)
from app.modules.datasets.infrastructure import DatasetExportModel, DatasetExportRepository
from app.modules.datasets.service import DatasetExportService, DatasetExportWorker
from app.modules.datasets.storage import LocalDatasetArtifactStorage
from app.modules.events.infrastructure import DomainEventModel
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.dataset_export_reader import IdentityDatasetReader
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from app.modules.telemetry.dataset_export_reader import TelemetryDatasetReader
from app.modules.telemetry.infrastructure import TelemetrySampleModel
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def database(path: Path) -> tuple[sessionmaker[Session], Session]:
    engine = create_engine(f"sqlite+pysqlite:///{path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return sessions, sessions()


def seed(db: Session, role: HumanRole = HumanRole.PLATFORM_ADMINISTRATOR) -> tuple[User, UUID]:
    facility_id, station_id, connector_id = uuid4(), uuid4(), uuid4()
    db.add(
        FacilityModel(
            id=facility_id,
            name=f"Facility {facility_id}",
            facility_type="University",
            timezone="UTC",
            country="Brazil",
            city="Juiz de Fora",
            address="Campus",
            operating_hours=None,
            status="Active",
        )
    )
    db.add(
        ChargingStationModel(
            id=station_id,
            facility_id=facility_id,
            name="Station",
            serial_number=str(station_id),
            maximum_power_kw=22,
            status="Available",
        )
    )
    db.add(
        ConnectorModel(
            id=connector_id,
            charging_station_id=station_id,
            connector_type="Type2",
            maximum_power_kw=22,
            status="Available",
        )
    )
    user = User.create(
        email=f"{uuid4()}@example.com",
        display_name="Exporter",
        password_hash="hash",
        account_type=AccountType.HUMAN,
        status=AccountStatus.ACTIVE,
        roles=[role],
        facility_ids=[facility_id] if role == HumanRole.FACILITY_OPERATOR else [],
    )
    db.commit()
    SqlAlchemyUserRepository(db).add(user)
    vehicle_id, reservation_id, session_id = uuid4(), uuid4(), uuid4()
    db.add(
        VehicleModel(
            id=vehicle_id,
            owner_id=user.id,
            display_name="Vehicle",
            status="ACTIVE",
        )
    )
    db.commit()
    db.add(
        ReservationModel(
            id=reservation_id,
            owner_id=user.id,
            vehicle_id=vehicle_id,
            connector_id=connector_id,
            start_at=dt("2026-07-20T10:00Z"),
            end_at=dt("2026-07-20T12:00Z"),
            status="COMPLETED",
        )
    )
    db.commit()
    db.add(
        ChargingSessionModel(
            id=session_id,
            reservation_id=reservation_id,
            owner_id=user.id,
            vehicle_id=vehicle_id,
            connector_id=connector_id,
            status="COMPLETED",
            started_at=dt("2026-07-20T10:10Z"),
            ended_at=dt("2026-07-20T11:40Z"),
        )
    )
    db.commit()
    db.add_all(
        [
            TelemetrySampleModel(
                id=uuid4(),
                session_id=session_id,
                sample_id="sample-1",
                source="API_CLIENT",
                recorded_at=dt("2026-07-20T11:00Z"),
                received_at=dt("2026-07-20T11:01Z"),
                power_kw=11.0,
                energy_kwh=None,
                state_of_charge_percent=50.0,
                created_at=dt("2026-07-20T11:01Z"),
            ),
            TelemetrySampleModel(
                id=uuid4(),
                session_id=session_id,
                sample_id="late-sample",
                source="API_CLIENT",
                recorded_at=dt("2026-07-20T11:30Z"),
                received_at=dt("2026-07-22T00:00Z"),
                power_kw=12.0,
                energy_kwh=None,
                state_of_charge_percent=55.0,
                created_at=dt("2026-07-22T00:00Z"),
            ),
        ]
    )
    db.commit()
    return user, facility_id


def settings(storage: Path, **overrides: object) -> Settings:
    configured = Settings(
        DATASET_EXPORT_STORAGE_PATH=str(storage),
        DATASET_EXPORT_PSEUDONYMIZATION_SECRET="test-secret",
    )
    return configured.model_copy(
        update={key.lower(): value for key, value in dict[str, Any](overrides).items()}
    )


def make_worker(
    sessions: sessionmaker[Session], configured: Settings, storage: LocalDatasetArtifactStorage
) -> DatasetExportWorker:
    return DatasetExportWorker(
        sessions,
        configured,
        storage,
        ChargingDatasetReader,
        TelemetryDatasetReader,
        lambda session: AnalyticsService(AnalyticsRepository(session)),
        IdentityDatasetReader,
    )


def test_worker_generates_artifact_and_completed_event(tmp_path: Path) -> None:
    sessions, db = database(tmp_path / "worker.db")
    user, facility_id = seed(db)
    request = CreateExport.new(
        dataset_type=DatasetType.OPERATIONAL_TELEMETRY,
        export_profile=ExportProfile.RESEARCH,
        format=ExportFormat.CSV,
        filters=ExportFilters(
            dt("2026-07-20T00:00Z"), dt("2026-07-21T00:00Z"), facility_id=facility_id
        ),
        requested_by=user.id,
    )
    DatasetExportRepository(db).create(request)
    storage = LocalDatasetArtifactStorage(tmp_path / "artifacts")
    worker = make_worker(sessions, settings(tmp_path / "artifacts"), storage)
    assert worker.process(request.id)
    with sessions() as verify:
        item = verify.get(DatasetExportModel, request.id)
        assert item is not None
        assert item.status == ExportStatus.COMPLETED.value
        assert item.data_cutoff_at is not None
        assert item.row_count == 1
        assert item.artifact_sha256 and len(item.artifact_sha256) == 64
        event = verify.scalar(
            select(DomainEventModel).where(
                DomainEventModel.event_type == "dataset-export.completed"
            )
        )
        assert event is not None
        assert event.payload["dataset_export_id"] == str(request.id)
        key = item.artifact_storage_key
        assert key is not None
    with storage.open(key) as artifact, zipfile.ZipFile(io.BytesIO(artifact.read())) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        assert set(bundle.namelist()) == {"manifest.json", "data.csv"}
        assert manifest["pseudonymization"]["applied"] is True
        assert str(user.id) not in bundle.read("data.csv").decode()


def test_claiming_runtime_limit_recovery_and_expiration(tmp_path: Path) -> None:
    sessions, db = database(tmp_path / "lifecycle.db")
    user, facility_id = seed(db)
    request = CreateExport.new(
        dataset_type=DatasetType.OPERATIONAL_CHARGING_SESSIONS,
        export_profile=ExportProfile.ADMINISTRATIVE,
        format=ExportFormat.CSV,
        filters=ExportFilters(
            dt("2026-07-20T00:00Z"), dt("2026-07-21T00:00Z"), facility_id=facility_id
        ),
        requested_by=user.id,
    )
    repo = DatasetExportRepository(db)
    repo.create(request)
    started = datetime.now(UTC) - timedelta(hours=2)
    assert repo.claim(request.id, started)
    assert not repo.claim(request.id, started)
    worker = make_worker(
        sessions,
        settings(tmp_path / "artifacts", DATASET_EXPORT_ABANDONED_TIMEOUT_SECONDS=1),
        LocalDatasetArtifactStorage(tmp_path / "artifacts"),
    )
    assert worker.recover(snapshot_lost=True) == 1
    with sessions() as verify:
        item = verify.get(DatasetExportModel, request.id)
        assert item is not None
        assert item.status == ExportStatus.FAILED.value
        assert item.failure_code == FailureCode.SNAPSHOT_LOST.value

    abandoned = CreateExport.new(
        dataset_type=DatasetType.OPERATIONAL_CHARGING_SESSIONS,
        export_profile=ExportProfile.ADMINISTRATIVE,
        format=ExportFormat.CSV,
        filters=request.filters,
        requested_by=user.id,
    )
    pending = CreateExport.new(
        dataset_type=DatasetType.OPERATIONAL_CHARGING_SESSIONS,
        export_profile=ExportProfile.ADMINISTRATIVE,
        format=ExportFormat.CSV,
        filters=request.filters,
        requested_by=user.id,
    )
    with sessions() as mutate:
        repo = DatasetExportRepository(mutate)
        repo.create(abandoned)
        assert repo.claim(abandoned.id, started)
        repo.create(pending)
    assert worker.recover(snapshot_lost=False) == 1
    assert worker.drain_pending() == 1
    with sessions() as verify:
        abandoned_item = verify.get(DatasetExportModel, abandoned.id)
        pending_item = verify.get(DatasetExportModel, pending.id)
        assert abandoned_item is not None and pending_item is not None
        assert abandoned_item.failure_code == FailureCode.ABANDONED_PROCESSING.value
        assert pending_item.status == ExportStatus.COMPLETED.value

        pending_item.artifact_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        storage_key = pending_item.artifact_storage_key
        verify.commit()
    assert storage_key is not None
    storage = LocalDatasetArtifactStorage(tmp_path / "artifacts")
    with sessions() as cleanup_session:
        service = DatasetExportService(
            cleanup_session,
            settings(tmp_path / "artifacts"),
            storage,
            ChargingDatasetReader(cleanup_session),
        )
        assert service.cleanup_expired() == 1
    assert not storage.exists(storage_key)


def test_runtime_row_and_artifact_limits_fail_with_closed_codes(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    sessions, db = database(tmp_path / "limits.db")
    user, facility_id = seed(db)

    def request() -> CreateExport:
        return CreateExport.new(
            dataset_type=DatasetType.OPERATIONAL_CHARGING_SESSIONS,
            export_profile=ExportProfile.ADMINISTRATIVE,
            format=ExportFormat.CSV,
            filters=ExportFilters(
                dt("2026-07-20T00:00Z"),
                dt("2026-07-21T00:00Z"),
                facility_id=facility_id,
            ),
            requested_by=user.id,
        )

    row_limited = request()
    DatasetExportRepository(db).create(row_limited)
    row_worker = make_worker(
        sessions,
        settings(tmp_path / "row-artifacts", DATASET_EXPORT_MAX_ROWS=1),
        LocalDatasetArtifactStorage(tmp_path / "row-artifacts"),
    )
    monkeypatch.setattr(row_worker, "_rows", lambda *_args: [{}, {}])
    assert row_worker.process(row_limited.id)

    size_limited = request()
    DatasetExportRepository(db).create(size_limited)
    size_worker = make_worker(
        sessions,
        settings(tmp_path / "size-artifacts", DATASET_EXPORT_MAX_ARTIFACT_SIZE_BYTES=1),
        LocalDatasetArtifactStorage(tmp_path / "size-artifacts"),
    )
    assert size_worker.process(size_limited.id)

    with sessions() as verify:
        row_item = verify.get(DatasetExportModel, row_limited.id)
        size_item = verify.get(DatasetExportModel, size_limited.id)
        assert row_item is not None and size_item is not None
        assert row_item.failure_code == FailureCode.ROW_LIMIT_EXCEEDED.value
        assert size_item.failure_code == FailureCode.ARTIFACT_SIZE_LIMIT_EXCEEDED.value
        assert row_item.artifact_storage_key is None
        assert size_item.artifact_storage_key is None


def test_api_authorization_inference_visibility_and_download(tmp_path: Path) -> None:
    sessions, db = database(tmp_path / "api.db")
    operator, facility_id = seed(db, HumanRole.FACILITY_OPERATOR)
    _other_admin, other_facility_id = seed(db)
    other_station_id = db.scalar(
        select(ChargingStationModel.id).where(ChargingStationModel.facility_id == other_facility_id)
    )
    assert other_station_id is not None
    configured = settings(tmp_path / "api-artifacts")
    app = FastAPI()
    app.include_router(router)

    def db_dependency() -> Generator[Session]:
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = db_dependency
    app.dependency_overrides[current_user] = lambda: operator
    app.dependency_overrides[get_settings] = lambda: configured
    with TestClient(app) as client:
        created = client.post(
            "/dataset-exports",
            json={
                "dataset_type": "OPERATIONAL_CHARGING_SESSIONS",
                "export_profile": "ADMINISTRATIVE",
                "format": "CSV",
                "filters": {
                    "from": "2026-07-20T00:00:00Z",
                    "to": "2026-07-21T00:00:00Z",
                },
            },
        )
        assert created.status_code == 202
        export_id = created.json()["id"]
        assert created.json()["status"] == "PENDING"
        assert created.json()["data_cutoff_at"] is None
        assert created.headers["location"] == f"/dataset-exports/{export_id}"
        detail = client.get(f"/dataset-exports/{export_id}")
        assert detail.status_code == 200
        assert detail.json()["filters"]["facility_id"] == str(facility_id)
        assert detail.json()["status"] == "COMPLETED"
        downloaded = client.get(f"/dataset-exports/{export_id}/download")
        assert downloaded.status_code == 200
        assert downloaded.headers["content-type"] == "application/zip"
        assert downloaded.headers["etag"].startswith('"')

        pending = CreateExport.new(
            dataset_type=DatasetType.OPERATIONAL_CHARGING_SESSIONS,
            export_profile=ExportProfile.ADMINISTRATIVE,
            format=ExportFormat.CSV,
            filters=ExportFilters(
                dt("2026-07-20T00:00Z"),
                dt("2026-07-21T00:00Z"),
                facility_id=facility_id,
            ),
            requested_by=operator.id,
        )
        failed = CreateExport.new(
            dataset_type=DatasetType.OPERATIONAL_CHARGING_SESSIONS,
            export_profile=ExportProfile.ADMINISTRATIVE,
            format=ExportFormat.CSV,
            filters=pending.filters,
            requested_by=operator.id,
        )
        with sessions() as mutate:
            repo = DatasetExportRepository(mutate)
            repo.create(pending)
            repo.create(failed)
            assert repo.claim(failed.id, datetime.now(UTC))
            repo.fail(failed.id, FailureCode.GENERATION_FAILURE, "Dataset generation failed.")
        assert client.get(f"/dataset-exports/{pending.id}/download").status_code == 409
        failed_detail = client.get(f"/dataset-exports/{failed.id}")
        assert failed_detail.status_code == 200
        assert failed_detail.json()["failure_code"] == "GENERATION_FAILURE"
        failed_list = client.get("/dataset-exports", params={"status": "FAILED", "limit": 1})
        assert failed_list.status_code == 200
        assert failed_list.json()["total"] == 1
        assert failed_list.json()["items"][0]["id"] == str(failed.id)
        page = client.get("/dataset-exports", params={"limit": 1, "offset": 1})
        assert page.status_code == 200
        assert page.json()["total"] == 3
        assert len(page.json()["items"]) == 1

        with sessions() as mutate:
            item = mutate.get(DatasetExportModel, UUID(export_id))
            assert item is not None
            item.artifact_expires_at = datetime.now(UTC) - timedelta(seconds=1)
            mutate.commit()
        assert client.get(f"/dataset-exports/{export_id}/download").status_code == 410

        with sessions() as mutate:
            item = mutate.get(DatasetExportModel, UUID(export_id))
            assert item is not None and item.artifact_storage_key is not None
            item.artifact_expires_at = datetime.now(UTC) + timedelta(days=1)
            storage_key = item.artifact_storage_key
            mutate.commit()
        LocalDatasetArtifactStorage(tmp_path / "api-artifacts").delete(storage_key)
        assert client.get(f"/dataset-exports/{export_id}/download").status_code == 503

        ambiguous = User(
            **{
                **operator.__dict__,
                "facility_ids": (facility_id, uuid4()),
            }
        )
        app.dependency_overrides[current_user] = lambda: ambiguous
        assert (
            client.post(
                "/dataset-exports",
                json={
                    "dataset_type": "OPERATIONAL_CHARGING_SESSIONS",
                    "export_profile": "ADMINISTRATIVE",
                    "format": "CSV",
                    "filters": {
                        "from": "2026-07-20T00:00:00Z",
                        "to": "2026-07-21T00:00:00Z",
                    },
                },
            ).status_code
            == 400
        )

        app.dependency_overrides[current_user] = lambda: operator.with_facilities([])
        assert client.get(f"/dataset-exports/{export_id}").status_code == 404

        administrator_operator = replace(
            operator,
            roles=(HumanRole.FACILITY_OPERATOR, HumanRole.PLATFORM_ADMINISTRATOR),
            facility_ids=(),
        )
        app.dependency_overrides[current_user] = lambda: administrator_operator
        assert client.get(f"/dataset-exports/{export_id}").status_code == 200

        other_operator = User.create(
            email=f"{uuid4()}@example.com",
            display_name="Other operator",
            password_hash="hash",
            account_type=AccountType.HUMAN,
            status=AccountStatus.ACTIVE,
            roles=[HumanRole.FACILITY_OPERATOR],
            facility_ids=[facility_id],
        )
        app.dependency_overrides[current_user] = lambda: other_operator
        assert client.get(f"/dataset-exports/{export_id}").status_code == 404

        app.dependency_overrides[current_user] = lambda: operator
        unauthorized = client.post(
            "/dataset-exports",
            json={
                "dataset_type": "OPERATIONAL_CHARGING_SESSIONS",
                "export_profile": "RESEARCH",
                "format": "CSV",
                "filters": {
                    "from": "2026-07-20T00:00:00Z",
                    "to": "2026-07-21T00:00:00Z",
                    "facility_id": str(other_facility_id),
                },
            },
        )
        assert unauthorized.status_code == 403
        mismatch = client.post(
            "/dataset-exports",
            json={
                "dataset_type": "OPERATIONAL_CHARGING_SESSIONS",
                "export_profile": "ADMINISTRATIVE",
                "format": "CSV",
                "filters": {
                    "from": "2026-07-20T00:00:00Z",
                    "to": "2026-07-21T00:00:00Z",
                    "facility_id": str(facility_id),
                    "station_id": str(other_station_id),
                },
            },
        )
        assert mismatch.status_code == 400

        common = {
            "dataset_type": "OPERATIONAL_CHARGING_SESSIONS",
            "export_profile": "ADMINISTRATIVE",
            "format": "CSV",
            "filters": {
                "from": "2026-07-20T00:00:00Z",
                "to": "2026-07-21T00:00:00Z",
                "timezone": "UTC",
            },
        }
        assert client.post("/dataset-exports", json=common).status_code == 422
        invalid_window = {
            **common,
            "filters": {
                "from": "2026-07-21T00:00:00Z",
                "to": "2026-07-20T00:00:00Z",
            },
        }
        assert client.post("/dataset-exports", json=invalid_window).status_code == 400
        assert (
            client.post("/dataset-exports", json={**common, "dataset_type": "INVALID"}).status_code
            == 422
        )
        assert (
            client.post(
                "/dataset-exports", json={**common, "export_profile": "INVALID"}
            ).status_code
            == 422
        )
        app.dependency_overrides[get_settings] = lambda: settings(
            tmp_path / "api-artifacts", DATASET_EXPORT_ENABLED_FORMATS="PARQUET"
        )
        disabled = {
            **common,
            "format": "CSV",
            "filters": {
                "from": "2026-07-20T00:00:00Z",
                "to": "2026-07-21T00:00:00Z",
            },
        }
        assert client.post("/dataset-exports", json=disabled).status_code == 422
        app.dependency_overrides[get_settings] = lambda: configured

        inactive = operator.with_profile(status=AccountStatus.INACTIVE)
        app.dependency_overrides[current_user] = lambda: inactive
        assert client.get("/dataset-exports").status_code == 403

        denied = User.create(
            email=f"{uuid4()}@example.com",
            display_name="Researcher",
            password_hash="hash",
            account_type=AccountType.HUMAN,
            status=AccountStatus.ACTIVE,
            roles=[HumanRole.RESEARCHER],
            facility_ids=[],
        )
        app.dependency_overrides[current_user] = lambda: denied
        assert client.get("/dataset-exports").status_code == 403
        assert client.get(f"/dataset-exports/{export_id}").status_code == 404
        for role in (HumanRole.DATA_SCIENTIST, HumanRole.EV_DRIVER):
            denied_role = replace(denied, id=uuid4(), roles=(role,))
            app.dependency_overrides[current_user] = lambda user=denied_role: user
            assert client.get("/dataset-exports").status_code == 403
        technical = replace(
            denied,
            id=uuid4(),
            account_type=AccountType.TECHNICAL_CLIENT,
            roles=(),
        )
        app.dependency_overrides[current_user] = lambda: technical
        assert client.get("/dataset-exports").status_code == 403


def test_analytics_projection_uses_explicit_processing_time(tmp_path: Path) -> None:
    _sessions, db = database(tmp_path / "analytics-cutoff.db")
    admin, facility_id = seed(db)
    connector = db.scalar(select(ConnectorModel))
    assert connector is not None
    vehicle_id, reservation_id = uuid4(), uuid4()
    db.add_all(
        [
            VehicleModel(
                id=vehicle_id,
                owner_id=admin.id,
                display_name="Active Vehicle",
                status="ACTIVE",
            ),
            ReservationModel(
                id=reservation_id,
                owner_id=admin.id,
                vehicle_id=vehicle_id,
                connector_id=connector.id,
                start_at=dt("2026-07-20T12:00Z"),
                end_at=dt("2026-07-20T15:00Z"),
                status="ACTIVE",
            ),
            ChargingSessionModel(
                id=uuid4(),
                reservation_id=reservation_id,
                owner_id=admin.id,
                vehicle_id=vehicle_id,
                connector_id=connector.id,
                status="ACTIVE",
                started_at=dt("2026-07-20T12:00Z"),
                ended_at=None,
            ),
        ]
    )
    db.commit()
    projection = AnalyticsService(AnalyticsRepository(db))
    query = AnalyticsQuery(
        dt("2026-07-20T00:00Z"),
        dt("2026-07-21T00:00Z"),
        facility_id=facility_id,
        granularity=Granularity.DAY,
    )
    first = projection.project_occupancy(query, admin, dt("2026-07-20T13:00Z"))
    second = projection.project_occupancy(query, admin, dt("2026-07-20T14:00Z"))
    assert len(first) == len(second) == 1
    assert second[0]["charging_duration_minutes"] - first[0]["charging_duration_minutes"] == 60


def test_openapi_documents_dataset_export_contract() -> None:
    app = FastAPI()
    app.include_router(router)
    schema = app.openapi()
    assert set(schema["paths"]) == {
        "/dataset-exports",
        "/dataset-exports/{dataset_export_id}",
        "/dataset-exports/{dataset_export_id}/download",
    }
    assert schema["paths"]["/dataset-exports"]["post"]["security"] == [{"HTTPBearer": []}]
    download = schema["paths"]["/dataset-exports/{dataset_export_id}/download"]["get"]
    assert set(download["responses"]["200"]["content"]) == {"application/zip"}
    schemas = schema["components"]["schemas"]
    assert schemas["DatasetType"]["enum"] == [item.value for item in DatasetType]
    assert schemas["FailureCode"]["enum"] == [item.value for item in FailureCode]


@pytest.mark.skipif(
    not os.getenv("POSTGRES_TEST_DATABASE_URL"),
    reason="POSTGRES_TEST_DATABASE_URL is required for snapshot and claiming tests",
)
def test_postgres_worker_uses_snapshot_and_atomic_claiming(tmp_path: Path) -> None:
    database_url = os.environ["POSTGRES_TEST_DATABASE_URL"]
    engine = create_engine(database_url, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with sessions() as db:
        user, facility_id = seed(db)
        request = CreateExport.new(
            dataset_type=DatasetType.OPERATIONAL_TELEMETRY,
            export_profile=ExportProfile.ADMINISTRATIVE,
            format=ExportFormat.PARQUET,
            filters=ExportFilters(
                dt("2026-07-20T00:00Z"),
                dt("2026-07-21T00:00Z"),
                facility_id=facility_id,
            ),
            requested_by=user.id,
        )
        DatasetExportRepository(db).create(request)
    worker = make_worker(
        sessions,
        settings(tmp_path / "postgres-artifacts"),
        LocalDatasetArtifactStorage(tmp_path / "postgres-artifacts"),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = (
            pool.submit(worker.process, request.id),
            pool.submit(worker.process, request.id),
        )
        outcomes = [future.result(timeout=15) for future in futures]
    assert sorted(outcomes) == [False, True]
    with sessions() as verify:
        item = verify.get(DatasetExportModel, request.id)
        assert item is not None
        assert item.status == ExportStatus.COMPLETED.value
        assert item.data_cutoff_at is not None
        assert item.row_count == 1

        source_session = verify.scalar(
            select(ChargingSessionModel).where(ChargingSessionModel.owner_id == user.id)
        )
        assert source_session is not None
        snapshot_request = CreateExport.new(
            dataset_type=DatasetType.OPERATIONAL_TELEMETRY,
            export_profile=ExportProfile.ADMINISTRATIVE,
            format=ExportFormat.CSV,
            filters=ExportFilters(
                dt("2026-07-20T00:00Z"),
                dt("2026-07-21T00:00Z"),
                facility_id=facility_id,
            ),
            requested_by=user.id,
        )
        DatasetExportRepository(verify).create(snapshot_request)

    snapshot_ready = Event()
    release_snapshot = Event()

    class BlockingIdentityReader:
        def __init__(self, session: Session) -> None:
            self.delegate = IdentityDatasetReader(session)

        def get_user(self, user_id: UUID) -> User | None:
            result = self.delegate.get_user(user_id)
            snapshot_ready.set()
            if not release_snapshot.wait(timeout=10):
                raise TimeoutError("snapshot test was not released")
            return result

    snapshot_worker = DatasetExportWorker(
        sessions,
        settings(tmp_path / "snapshot-artifacts"),
        LocalDatasetArtifactStorage(tmp_path / "snapshot-artifacts"),
        ChargingDatasetReader,
        TelemetryDatasetReader,
        lambda session: AnalyticsService(AnalyticsRepository(session)),
        BlockingIdentityReader,
    )
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(snapshot_worker.process, snapshot_request.id)
        assert snapshot_ready.wait(timeout=10)
        with sessions() as concurrent:
            concurrent.add(
                TelemetrySampleModel(
                    id=uuid4(),
                    session_id=source_session.id,
                    sample_id=f"committed-after-snapshot-{uuid4()}",
                    source="API_CLIENT",
                    recorded_at=dt("2026-07-20T11:15Z"),
                    received_at=dt("2026-07-20T11:16Z"),
                    power_kw=9.0,
                    energy_kwh=None,
                    state_of_charge_percent=52.0,
                    created_at=dt("2026-07-20T11:16Z"),
                )
            )
            concurrent.commit()
        release_snapshot.set()
        assert future.result(timeout=15)
    with sessions() as verify:
        snapshot_item = verify.get(DatasetExportModel, snapshot_request.id)
        assert snapshot_item is not None
        assert snapshot_item.status == ExportStatus.COMPLETED.value
        assert snapshot_item.row_count == 1
    engine.dispose()
