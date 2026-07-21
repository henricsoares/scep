from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any
from uuid import UUID

from opentelemetry import trace
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.modules.analytics.application.models import AnalyticsQuery, Granularity
from app.modules.analytics.application.ports import OccupancyProjectionPort
from app.modules.charging.application.dataset_export import ChargingDatasetReadPort
from app.modules.datasets.domain import (
    CreateExport,
    DatasetAuthorizationError,
    DatasetNotFoundError,
    DatasetQueueFullError,
    DatasetRuntimeError,
    DatasetType,
    DatasetUnsupportedError,
    DatasetValidationError,
    ExportFilters,
    ExportFormat,
    ExportProfile,
    ExportStatus,
    FailureCode,
)
from app.modules.datasets.infrastructure import DatasetExportModel, DatasetExportRepository
from app.modules.datasets.metrics import (
    artifact_size_bytes,
    currently_processing,
    expired_artifacts_total,
    export_failures_total,
    export_outcomes_total,
    export_requests_total,
    generated_rows,
    pending_duration_seconds,
    processing_duration_seconds,
    storage_failures_total,
)
from app.modules.datasets.schemas import build_artifact, transform_research
from app.modules.datasets.storage import ArtifactStorageError, DatasetArtifactStorage
from app.modules.events.contracts import dataset_export_completed_event
from app.modules.events.infrastructure import EventPublisher
from app.modules.identity.application.dataset_export import DatasetExportIdentityReadPort
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.telemetry.application.dataset_export import TelemetryDatasetReadPort

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class DatasetExportService:
    def __init__(
        self,
        session: Session,
        settings: Settings,
        storage: DatasetArtifactStorage,
        scope_reader: ChargingDatasetReadPort,
    ) -> None:
        self.session = session
        self.settings = settings
        self.storage = storage
        self.scope_reader = scope_reader
        self.repository = DatasetExportRepository(session)

    def create(
        self,
        *,
        dataset_type: DatasetType,
        profile: ExportProfile,
        format: ExportFormat,
        filters: ExportFilters,
        user: User,
    ) -> DatasetExportModel:
        export_requests_total.labels(dataset_type.value, profile.value, format.value).inc()
        try:
            resolved = self._validate(dataset_type, format, filters, user)
            if self.repository.count_pending() >= self.settings.dataset_export_max_queued_jobs:
                raise DatasetQueueFullError("dataset export queue is full")
            item = CreateExport.new(
                dataset_type=dataset_type,
                export_profile=profile,
                format=format,
                filters=resolved,
                requested_by=user.id,
            )
            model = self.repository.create(item)
            export_outcomes_total.labels(
                "accepted", dataset_type.value, profile.value, format.value
            ).inc()
            logger.info(
                "dataset_export_request_accepted",
                extra={"dataset_export_id": str(model.id)},
            )
            return model
        except Exception:
            export_outcomes_total.labels(
                "rejected", dataset_type.value, profile.value, format.value
            ).inc()
            raise

    def _validate(
        self,
        dataset_type: DatasetType,
        format: ExportFormat,
        filters: ExportFilters,
        user: User,
    ) -> ExportFilters:
        if user.status != AccountStatus.ACTIVE or user.account_type != AccountType.HUMAN:
            raise DatasetAuthorizationError("insufficient permission")
        admin = HumanRole.PLATFORM_ADMINISTRATOR in user.roles
        operator = HumanRole.FACILITY_OPERATOR in user.roles
        if not admin and not operator:
            raise DatasetAuthorizationError("insufficient permission")
        if filters.from_.tzinfo is None or filters.to.tzinfo is None:
            raise DatasetValidationError("from and to must include an explicit timezone offset")
        if filters.from_.astimezone(UTC) >= filters.to.astimezone(UTC):
            raise DatasetValidationError("from must be earlier than to")
        if filters.to.astimezone(UTC) - filters.from_.astimezone(UTC) > timedelta(
            days=self.settings.dataset_export_max_window_days
        ):
            raise DatasetValidationError("export window exceeds the configured maximum")
        enabled_formats = {
            value.strip().upper()
            for value in self.settings.dataset_export_enabled_formats.split(",")
            if value.strip()
        }
        if format.value not in enabled_formats:
            raise DatasetUnsupportedError("export format is disabled")
        if dataset_type == DatasetType.ANALYTICAL_OCCUPANCY:
            if filters.granularity not in {item.value for item in Granularity}:
                raise DatasetValidationError("granularity is required for analytical occupancy")
            if filters.session_id is not None:
                raise DatasetUnsupportedError("session_id is unsupported for this dataset type")
        elif filters.granularity is not None or filters.timezone is not None:
            raise DatasetUnsupportedError(
                "analytical filters are unsupported for this dataset type"
            )
        if dataset_type != DatasetType.OPERATIONAL_TELEMETRY and filters.session_id is not None:
            raise DatasetUnsupportedError("session_id is unsupported for this dataset type")

        facility_id = filters.facility_id
        if operator and not admin:
            if not user.facility_ids:
                raise DatasetAuthorizationError("facility operator has no Facility Assignment")
            if facility_id is None:
                if len(user.facility_ids) != 1:
                    raise DatasetValidationError(
                        "facility_id is required when assignment is ambiguous"
                    )
                facility_id = user.facility_ids[0]
            if facility_id not in user.facility_ids:
                raise DatasetAuthorizationError("facility is outside authorized scope")
        if (
            admin
            and dataset_type == DatasetType.ANALYTICAL_OCCUPANCY
            and facility_id is None
            and filters.timezone is None
        ):
            raise DatasetValidationError("timezone is required for multi-facility exports")
        resolved = ExportFilters(
            filters.from_,
            filters.to,
            facility_id,
            filters.station_id,
            filters.connector_id,
            filters.session_id,
            filters.timezone,
            filters.granularity,
        )
        try:
            self.scope_reader.validate_scope(
                facility_id=resolved.facility_id,
                station_id=resolved.station_id,
                connector_id=resolved.connector_id,
                session_id=resolved.session_id,
            )
        except ValueError as exc:
            raise DatasetValidationError(str(exc)) from exc
        except LookupError as exc:
            raise DatasetNotFoundError(str(exc)) from exc
        return resolved

    @staticmethod
    def can_access(item: DatasetExportModel, user: User) -> bool:
        if user.status != AccountStatus.ACTIVE or user.account_type != AccountType.HUMAN:
            return False
        if HumanRole.PLATFORM_ADMINISTRATOR in user.roles:
            return True
        if HumanRole.FACILITY_OPERATOR not in user.roles or item.requested_by != user.id:
            return False
        facility = item.filters.get("facility_id")
        return facility is not None and UUID(str(facility)) in user.facility_ids

    def cleanup_expired(self, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        cleaned = 0
        for item in self.repository.expired(now):
            key = item.artifact_storage_key
            if key:
                try:
                    self.storage.delete(key)
                except ArtifactStorageError:
                    storage_failures_total.labels("delete").inc()
                    continue
                self.repository.mark_artifact_deleted(item.id, now)
                expired_artifacts_total.inc()
                cleaned += 1
                logger.info(
                    "dataset_export_artifact_expired",
                    extra={"dataset_export_id": str(item.id)},
                )
        return cleaned


class DatasetExportWorker:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        settings: Settings,
        storage: DatasetArtifactStorage,
        charging_readers: Callable[[Session], ChargingDatasetReadPort],
        telemetry_readers: Callable[[Session], TelemetryDatasetReadPort],
        analytics_projections: Callable[[Session], OccupancyProjectionPort],
        identity_readers: Callable[[Session], DatasetExportIdentityReadPort],
    ) -> None:
        self.sessions = sessions
        self.settings = settings
        self.storage = storage
        self.charging_readers = charging_readers
        self.telemetry_readers = telemetry_readers
        self.analytics_projections = analytics_projections
        self.identity_readers = identity_readers

    def process(self, export_id: UUID) -> bool:
        started = datetime.now(UTC)
        with self.sessions() as metadata:
            repo = DatasetExportRepository(metadata)
            if metadata.get_bind().dialect.name == "postgresql":
                metadata.execute(text("SELECT pg_advisory_xact_lock(834728114)"))
            active = int(
                metadata.scalar(
                    select(func.count())
                    .select_from(DatasetExportModel)
                    .where(DatasetExportModel.status == ExportStatus.PROCESSING.value)
                )
                or 0
            )
            if active >= self.settings.dataset_export_max_concurrent_jobs:
                return False
            if not repo.claim(export_id, started):
                return False
            item = repo.get(export_id)
            if item is None:
                raise RuntimeError("claimed Dataset Export disappeared")
            pending_duration_seconds.observe(
                max(0.0, (started - utc(item.created_at)).total_seconds())
            )
        currently_processing.inc()
        began = monotonic()
        logger.info(
            "dataset_export_processing_started",
            extra={"dataset_export_id": str(export_id)},
        )
        try:
            with tracer.start_as_current_span("dataset_export.process") as span:
                span.set_attribute("dataset.export_id", str(export_id))
                span.set_attribute("dataset.type", item.dataset_type)
                self._generate(export_id, began)
            return True
        finally:
            currently_processing.dec()
            processing_duration_seconds.observe(monotonic() - began)

    def process_and_drain(self, export_id: UUID) -> int:
        processed = int(self.process(export_id))
        while True:
            with self.sessions() as session:
                items, _ = DatasetExportRepository(session).list(
                    status=ExportStatus.PENDING, limit=1
                )
                next_id = items[0].id if items else None
            if next_id is None or not self.process(next_id):
                return processed
            processed += 1

    def _generate(self, export_id: UUID, began: float) -> None:
        key: str | None = None
        try:
            with self.sessions() as source:
                if source.get_bind().dialect.name == "postgresql":
                    source.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                    source.execute(text("SET TRANSACTION READ ONLY"))
                    cutoff = source.scalar(select(func.transaction_timestamp()))
                else:
                    source.connection()
                    cutoff = datetime.now(UTC)
                if cutoff is None:
                    raise DatasetRuntimeError(
                        FailureCode.SNAPSHOT_LOST, "Source snapshot could not be established."
                    )
                if cutoff.tzinfo is None:
                    cutoff = cutoff.replace(tzinfo=UTC)
                with self.sessions() as metadata:
                    DatasetExportRepository(metadata).set_cutoff(export_id, cutoff)
                    item = DatasetExportRepository(metadata).get(export_id)
                    if item is None:
                        raise DatasetRuntimeError(
                            FailureCode.GENERATION_FAILURE, "Dataset generation failed."
                        )
                    filters = ExportFilters.from_canonical(item.filters)
                    user = self.identity_readers(source).get_user(item.requested_by)
                    if user is None:
                        raise DatasetRuntimeError(
                            FailureCode.GENERATION_FAILURE, "Dataset generation failed."
                        )
                rows = self._rows(source, item, filters, user, cutoff)
                if len(rows) > self.settings.dataset_export_max_rows:
                    raise DatasetRuntimeError(
                        FailureCode.ROW_LIMIT_EXCEEDED, "Generated row limit exceeded."
                    )
                if monotonic() - began > self.settings.dataset_export_processing_timeout_seconds:
                    raise DatasetRuntimeError(
                        FailureCode.PROCESSING_TIMEOUT, "Dataset processing timed out."
                    )
                if ExportProfile(item.export_profile) == ExportProfile.RESEARCH:
                    rows = transform_research(
                        rows,
                        DatasetType(item.dataset_type),
                        item.id,
                        self.settings.dataset_export_pseudonymization_secret,
                    )
                generated_at = datetime.now(UTC)
                artifact, data, _manifest = build_artifact(
                    export_id=item.id,
                    dataset_type=DatasetType(item.dataset_type),
                    profile=ExportProfile(item.export_profile),
                    format=ExportFormat(item.format),
                    filters=filters,
                    rows=rows,
                    data_cutoff_at=cutoff,
                    generated_at=generated_at,
                    application_version=self.settings.app_version,
                    source_revision=self.settings.source_revision,
                    key_version=self.settings.dataset_export_pseudonymization_key_version,
                )
                if len(artifact) > self.settings.dataset_export_max_artifact_size_bytes:
                    raise DatasetRuntimeError(
                        FailureCode.ARTIFACT_SIZE_LIMIT_EXCEEDED,
                        "Generated artifact size limit exceeded.",
                    )
                key = self.storage.store(item.id, artifact)
                logger.info(
                    "dataset_export_artifact_stored", extra={"dataset_export_id": str(item.id)}
                )
                completed = datetime.now(UTC)
                with self.sessions() as metadata:
                    completed_item = metadata.get(DatasetExportModel, item.id)
                    if completed_item is None:
                        raise DatasetRuntimeError(
                            FailureCode.GENERATION_FAILURE, "Dataset generation failed."
                        )
                    completed_item.status = ExportStatus.COMPLETED.value
                    completed_item.completed_at = completed
                    completed_item.row_count = len(rows)
                    completed_item.data_file_sha256 = hashlib.sha256(data).hexdigest()
                    completed_item.artifact_sha256 = hashlib.sha256(artifact).hexdigest()
                    completed_item.artifact_size_bytes = len(artifact)
                    completed_item.artifact_storage_key = key
                    completed_item.artifact_expires_at = completed + timedelta(
                        days=self.settings.dataset_export_retention_days
                    )
                    EventPublisher(metadata).publish(dataset_export_completed_event(completed_item))
                    metadata.commit()
                generated_rows.observe(len(rows))
                artifact_size_bytes.observe(len(artifact))
                export_outcomes_total.labels(
                    "completed", item.dataset_type, item.export_profile, item.format
                ).inc()
                logger.info(
                    "dataset_export_processing_completed",
                    extra={"dataset_export_id": str(item.id), "row_count": len(rows)},
                )
        except DatasetRuntimeError as exc:
            self._fail(export_id, exc.code, str(exc), key)
        except ArtifactStorageError:
            storage_failures_total.labels("store").inc()
            self._fail(export_id, FailureCode.STORAGE_FAILURE, "Artifact storage failed.", key)
        except Exception:
            logger.exception(
                "dataset_export_internal_generation_error",
                extra={"dataset_export_id": str(export_id)},
            )
            self._fail(export_id, FailureCode.GENERATION_FAILURE, "Dataset generation failed.", key)

    def _rows(
        self,
        source: Session,
        item: DatasetExportModel,
        filters: ExportFilters,
        user: User,
        cutoff: datetime,
    ) -> list[dict[str, Any]]:
        dataset_type = DatasetType(item.dataset_type)
        start = filters.from_.astimezone(UTC)
        end = filters.to.astimezone(UTC)
        if dataset_type == DatasetType.OPERATIONAL_CHARGING_SESSIONS:
            return [
                asdict(row)
                for row in self.charging_readers(source).charging_sessions(
                    start=start,
                    end=end,
                    facility_id=filters.facility_id,
                    station_id=filters.station_id,
                    connector_id=filters.connector_id,
                )
            ]
        if dataset_type == DatasetType.OPERATIONAL_TELEMETRY:
            return [
                asdict(row)
                for row in self.telemetry_readers(source).telemetry(
                    start=start,
                    end=end,
                    facility_id=filters.facility_id,
                    station_id=filters.station_id,
                    connector_id=filters.connector_id,
                    cutoff=cutoff,
                    session_id=filters.session_id,
                )
            ]
        query = AnalyticsQuery(
            filters.from_,
            filters.to,
            filters.facility_id,
            filters.station_id,
            filters.connector_id,
            filters.timezone,
            Granularity(filters.granularity or "hour"),
        )
        return self.analytics_projections(source).project_occupancy(query, user, cutoff)

    def _fail(
        self, export_id: UUID, code: FailureCode, message: str, storage_key: str | None
    ) -> None:
        if storage_key:
            try:
                self.storage.delete(storage_key)
            except ArtifactStorageError:
                storage_failures_total.labels("delete").inc()
        with self.sessions() as metadata:
            item = DatasetExportRepository(metadata).get(export_id)
            if item is not None:
                DatasetExportRepository(metadata).fail(export_id, code, message)
                export_outcomes_total.labels(
                    "failed", item.dataset_type, item.export_profile, item.format
                ).inc()
        export_failures_total.labels(code.value).inc()
        logger.warning(
            "dataset_export_processing_failed",
            extra={"dataset_export_id": str(export_id), "failure_code": code.value},
        )

    def recover(self, *, snapshot_lost: bool = True) -> int:
        threshold = datetime.now(UTC) - timedelta(
            seconds=self.settings.dataset_export_abandoned_timeout_seconds
        )
        with self.sessions() as session:
            count = DatasetExportRepository(session).recover_processing(
                threshold, snapshot_lost=snapshot_lost
            )
        if count:
            logger.warning(
                "dataset_export_abandoned_processing_recovered",
                extra={"recovered_count": count},
            )
        return count

    def drain_pending(self, *, limit: int = 100) -> int:
        with self.sessions() as session:
            items, _ = DatasetExportRepository(session).list(
                status=ExportStatus.PENDING, limit=limit
            )
            ids = [item.id for item in reversed(items)]
        return sum(1 for export_id in ids if self.process(export_id))
