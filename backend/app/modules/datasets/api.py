from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.infrastructure.database import get_db
from app.modules.analytics.application.service import AnalyticsService
from app.modules.analytics.infrastructure.repository import AnalyticsRepository
from app.modules.charging.infrastructure.dataset_export_reader import ChargingDatasetReader
from app.modules.datasets.domain import (
    DatasetAuthorizationError,
    DatasetNotFoundError,
    DatasetQueueFullError,
    DatasetType,
    DatasetUnsupportedError,
    DatasetValidationError,
    ExportFilters,
    ExportFormat,
    ExportProfile,
    ExportStatus,
    FailureCode,
    category,
)
from app.modules.datasets.infrastructure import DatasetExportModel, DatasetExportRepository
from app.modules.datasets.metrics import downloads_total, storage_failures_total
from app.modules.datasets.service import DatasetExportService, DatasetExportWorker
from app.modules.datasets.storage import (
    ArtifactStorageError,
    DatasetArtifactStorage,
    LocalDatasetArtifactStorage,
)
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.application.metrics import authorization_denied_total
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.dataset_export_reader import IdentityDatasetReader
from app.modules.telemetry.dataset_export_reader import TelemetryDatasetReader

router = APIRouter(prefix="/dataset-exports", tags=["Dataset Exports"])
logger = logging.getLogger(__name__)


class ExportFiltersRequest(BaseModel):
    from_: datetime = Field(alias="from", description="Inclusive boundary with explicit offset")
    to: datetime = Field(description="Exclusive boundary with explicit offset")
    facility_id: UUID | None = None
    station_id: UUID | None = None
    connector_id: UUID | None = None
    session_id: UUID | None = None
    timezone: str | None = None
    granularity: str | None = None
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    def domain(self) -> ExportFilters:
        return ExportFilters(
            self.from_,
            self.to,
            self.facility_id,
            self.station_id,
            self.connector_id,
            self.session_id,
            self.timezone,
            self.granularity,
        )


class CreateDatasetExportRequest(BaseModel):
    dataset_type: DatasetType
    export_profile: ExportProfile
    format: ExportFormat
    filters: ExportFiltersRequest
    model_config = ConfigDict(extra="forbid")


class CreateDatasetExportResponse(BaseModel):
    id: UUID
    dataset_type: DatasetType
    export_profile: ExportProfile
    format: ExportFormat
    status: ExportStatus
    schema_version: str
    data_cutoff_at: datetime | None
    created_at: datetime


class DatasetExportListItem(BaseModel):
    id: UUID
    dataset_type: DatasetType
    export_profile: ExportProfile
    format: ExportFormat
    status: ExportStatus
    row_count: int | None
    artifact_available: bool
    created_at: datetime
    completed_at: datetime | None


class DatasetExportListResponse(BaseModel):
    items: list[DatasetExportListItem]
    limit: int
    offset: int
    total: int


class DatasetExportDetailResponse(BaseModel):
    id: UUID
    requested_by: UUID
    dataset_type: DatasetType
    dataset_category: str
    export_profile: ExportProfile
    format: ExportFormat
    status: ExportStatus
    schema_version: str
    filters: dict[str, Any]
    data_cutoff_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    failure_code: FailureCode | None
    failure_message: str | None
    row_count: int | None
    data_file_sha256: str | None
    artifact_sha256: str | None
    artifact_size_bytes: int | None
    artifact_available: bool
    artifact_expires_at: datetime | None


ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"description": "Invalid export configuration"},
    401: {"description": "Authentication required"},
    403: {"description": "Dataset Export access forbidden"},
    404: {"description": "Dataset Export not found"},
    409: {"description": "Artifact not available in the current lifecycle state"},
    410: {"description": "Artifact expired"},
    422: {"description": "Unsupported request schema or filter combination"},
    503: {"description": "Dataset Export storage unavailable"},
}


def _components(
    db: Session, settings: Settings
) -> tuple[DatasetExportService, DatasetExportWorker]:
    storage = LocalDatasetArtifactStorage(settings.dataset_export_storage_path)
    sessions = sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)
    return (
        DatasetExportService(db, settings, storage, ChargingDatasetReader(db)),
        DatasetExportWorker(
            sessions,
            settings,
            storage,
            ChargingDatasetReader,
            TelemetryDatasetReader,
            lambda session: AnalyticsService(AnalyticsRepository(session)),
            IdentityDatasetReader,
        ),
    )


def _require_role(user: User) -> None:
    if (
        user.status != AccountStatus.ACTIVE
        or user.account_type != AccountType.HUMAN
        or not any(
            role in user.roles
            for role in (HumanRole.PLATFORM_ADMINISTRATOR, HumanRole.FACILITY_OPERATOR)
        )
    ):
        authorization_denied_total.inc()
        logger.warning("dataset_export_authorization_failed")
        raise HTTPException(status_code=403, detail="insufficient permission")


def _available(
    item: DatasetExportModel,
    storage: DatasetArtifactStorage,
    now: datetime | None = None,
) -> bool:
    now = now or datetime.now(UTC)
    expires_at = item.artifact_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    retained = bool(
        item.status == ExportStatus.COMPLETED.value
        and item.artifact_storage_key
        and item.artifact_deleted_at is None
        and expires_at
        and expires_at > now
    )
    if not retained or item.artifact_storage_key is None:
        return False
    try:
        return storage.exists(item.artifact_storage_key)
    except ArtifactStorageError:
        storage_failures_total.labels("exists").inc()
        logger.warning(
            "dataset_export_artifact_availability_check_failed",
            extra={"dataset_export_id": str(item.id)},
        )
        return False


def _create_response(item: DatasetExportModel) -> CreateDatasetExportResponse:
    return CreateDatasetExportResponse.model_validate(
        {
            "id": item.id,
            "dataset_type": item.dataset_type,
            "export_profile": item.export_profile,
            "format": item.format,
            "status": item.status,
            "schema_version": item.schema_version,
            "data_cutoff_at": item.data_cutoff_at,
            "created_at": item.created_at,
        }
    )


def _detail(
    item: DatasetExportModel, storage: DatasetArtifactStorage
) -> DatasetExportDetailResponse:
    return DatasetExportDetailResponse.model_validate(
        {
            **{
                name: getattr(item, name)
                for name in DatasetExportDetailResponse.model_fields
                if hasattr(item, name)
            },
            "dataset_category": category(DatasetType(item.dataset_type)).value,
            "artifact_available": _available(item, storage),
        }
    )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CreateDatasetExportResponse,
    responses=ERRORS,
    summary="Create an asynchronous Dataset Export",
    description=(
        "Persists a PENDING export and returns immediately. Windows use [from, to). "
        "Facility Operators are restricted to exactly one assigned Facility."
    ),
)
def create_dataset_export(
    request: CreateDatasetExportRequest,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> CreateDatasetExportResponse:
    service, worker = _components(db, settings)
    try:
        item = service.create(
            dataset_type=request.dataset_type,
            profile=request.export_profile,
            format=request.format,
            filters=request.filters.domain(),
            user=user,
        )
    except DatasetAuthorizationError as exc:
        authorization_denied_total.inc()
        logger.warning("dataset_export_authorization_failed")
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except DatasetUnsupportedError as exc:
        logger.warning("dataset_export_validation_failed", extra={"reason": "unsupported"})
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except DatasetNotFoundError as exc:
        logger.warning("dataset_export_validation_failed", extra={"reason": "not_found"})
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except DatasetValidationError as exc:
        logger.warning("dataset_export_validation_failed", extra={"reason": "invalid"})
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DatasetQueueFullError as exc:
        logger.warning("dataset_export_validation_failed", extra={"reason": "queue_full"})
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    response.headers["Location"] = f"/dataset-exports/{item.id}"
    background_tasks.add_task(worker.process_and_drain, item.id)
    return _create_response(item)


@router.get(
    "",
    response_model=DatasetExportListResponse,
    responses=ERRORS,
    summary="List visible Dataset Exports",
)
def list_dataset_exports(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
    export_status: Annotated[ExportStatus | None, Query(alias="status")] = None,
    dataset_type: DatasetType | None = None,
    export_profile: ExportProfile | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DatasetExportListResponse:
    _require_role(user)
    storage = LocalDatasetArtifactStorage(settings.dataset_export_storage_path)
    admin = HumanRole.PLATFORM_ADMINISTRATOR in user.roles
    repo = DatasetExportRepository(db)

    def query(page_limit: int, page_offset: int) -> tuple[list[DatasetExportModel], int]:
        return repo.list(
            requested_by=None if admin else user.id,
            status=export_status,
            dataset_type=dataset_type,
            export_profile=export_profile,
            created_from=created_from,
            created_to=created_to,
            limit=page_limit,
            offset=page_offset,
        )

    if admin:
        visible, total = query(limit, offset)
    else:
        owned, _ = query(1_000_000, 0)
        all_visible = [item for item in owned if DatasetExportService.can_access(item, user)]
        total = len(all_visible)
        visible = all_visible[offset : offset + limit]
    return DatasetExportListResponse(
        items=[
            DatasetExportListItem.model_validate(
                {
                    "id": item.id,
                    "dataset_type": item.dataset_type,
                    "export_profile": item.export_profile,
                    "format": item.format,
                    "status": item.status,
                    "row_count": item.row_count,
                    "artifact_available": _available(item, storage),
                    "created_at": item.created_at,
                    "completed_at": item.completed_at,
                }
            )
            for item in visible
        ],
        limit=limit,
        offset=offset,
        total=total,
    )


def _visible_item(db: Session, export_id: UUID, user: User) -> DatasetExportModel:
    item = DatasetExportRepository(db).get(export_id)
    if item is None or not DatasetExportService.can_access(item, user):
        raise HTTPException(status_code=404, detail="dataset export not found")
    return item


@router.get(
    "/{dataset_export_id}",
    response_model=DatasetExportDetailResponse,
    responses=ERRORS,
    summary="Retrieve Dataset Export metadata",
)
def retrieve_dataset_export(
    dataset_export_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetExportDetailResponse:
    storage = LocalDatasetArtifactStorage(settings.dataset_export_storage_path)
    return _detail(_visible_item(db, dataset_export_id, user), storage)


@router.get(
    "/{dataset_export_id}/download",
    response_class=StreamingResponse,
    responses=ERRORS | {200: {"content": {"application/zip": {}}, "description": "ZIP artifact"}},
    summary="Download a retained Dataset Export artifact",
)
def download_dataset_export(
    dataset_export_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    item = _visible_item(db, dataset_export_id, user)
    if item.status != ExportStatus.COMPLETED.value:
        downloads_total.labels("conflict").inc()
        raise HTTPException(status_code=409, detail="artifact is not available")
    now = datetime.now(UTC)
    expires_at = item.artifact_expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if item.artifact_deleted_at is not None or (expires_at is not None and expires_at <= now):
        downloads_total.labels("expired").inc()
        raise HTTPException(status_code=410, detail="artifact expired")
    if item.artifact_storage_key is None:
        downloads_total.labels("missing").inc()
        raise HTTPException(status_code=503, detail="artifact is unexpectedly unavailable")
    storage = LocalDatasetArtifactStorage(settings.dataset_export_storage_path)
    try:
        if not storage.exists(item.artifact_storage_key):
            raise ArtifactStorageError("artifact missing")
        stream = storage.open(item.artifact_storage_key)
    except ArtifactStorageError as exc:
        downloads_total.labels("storage_failure").inc()
        raise HTTPException(status_code=503, detail="artifact storage unavailable") from exc

    def chunks() -> Iterator[bytes]:
        with stream:
            while block := stream.read(64 * 1024):
                yield block

    downloads_total.labels("success").inc()
    filename = f"dataset-export-{item.id}.zip"
    return StreamingResponse(
        chunks(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "ETag": f'"{item.artifact_sha256}"',
        },
    )
