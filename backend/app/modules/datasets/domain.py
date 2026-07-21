from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class DatasetType(StrEnum):
    OPERATIONAL_CHARGING_SESSIONS = "OPERATIONAL_CHARGING_SESSIONS"
    OPERATIONAL_TELEMETRY = "OPERATIONAL_TELEMETRY"
    ANALYTICAL_OCCUPANCY = "ANALYTICAL_OCCUPANCY"


class DatasetCategory(StrEnum):
    OPERATIONAL = "OPERATIONAL"
    ANALYTICAL = "ANALYTICAL"


class ExportProfile(StrEnum):
    ADMINISTRATIVE = "ADMINISTRATIVE"
    RESEARCH = "RESEARCH"


class ExportFormat(StrEnum):
    CSV = "CSV"
    PARQUET = "PARQUET"


class ExportStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class FailureCode(StrEnum):
    ROW_LIMIT_EXCEEDED = "ROW_LIMIT_EXCEEDED"
    ARTIFACT_SIZE_LIMIT_EXCEEDED = "ARTIFACT_SIZE_LIMIT_EXCEEDED"
    PROCESSING_TIMEOUT = "PROCESSING_TIMEOUT"
    STORAGE_FAILURE = "STORAGE_FAILURE"
    GENERATION_FAILURE = "GENERATION_FAILURE"
    SNAPSHOT_LOST = "SNAPSHOT_LOST"
    ABANDONED_PROCESSING = "ABANDONED_PROCESSING"


class DatasetValidationError(ValueError):
    pass


class DatasetUnsupportedError(DatasetValidationError):
    pass


class DatasetAuthorizationError(ValueError):
    pass


class DatasetNotFoundError(ValueError):
    pass


class DatasetQueueFullError(RuntimeError):
    pass


class DatasetRuntimeError(RuntimeError):
    def __init__(self, code: FailureCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class ExportFilters:
    from_: datetime
    to: datetime
    facility_id: UUID | None = None
    station_id: UUID | None = None
    connector_id: UUID | None = None
    session_id: UUID | None = None
    timezone: str | None = None
    granularity: str | None = None

    def canonical(self) -> dict[str, Any]:
        def stamp(value: datetime) -> str:
            return value.astimezone(UTC).isoformat().replace("+00:00", "Z")

        return {
            "facility_id": str(self.facility_id) if self.facility_id else None,
            "station_id": str(self.station_id) if self.station_id else None,
            "connector_id": str(self.connector_id) if self.connector_id else None,
            "session_id": str(self.session_id) if self.session_id else None,
            "from": stamp(self.from_),
            "to": stamp(self.to),
            "timezone": self.timezone,
            "granularity": self.granularity,
        }

    @classmethod
    def from_canonical(cls, value: dict[str, Any]) -> ExportFilters:
        return cls(
            from_=datetime.fromisoformat(str(value["from"]).replace("Z", "+00:00")),
            to=datetime.fromisoformat(str(value["to"]).replace("Z", "+00:00")),
            facility_id=UUID(value["facility_id"]) if value.get("facility_id") else None,
            station_id=UUID(value["station_id"]) if value.get("station_id") else None,
            connector_id=UUID(value["connector_id"]) if value.get("connector_id") else None,
            session_id=UUID(value["session_id"]) if value.get("session_id") else None,
            timezone=value.get("timezone"),
            granularity=value.get("granularity"),
        )


@dataclass(frozen=True, slots=True)
class CreateExport:
    dataset_type: DatasetType
    export_profile: ExportProfile
    format: ExportFormat
    filters: ExportFilters
    requested_by: UUID
    id: UUID
    created_at: datetime

    @classmethod
    def new(
        cls,
        *,
        dataset_type: DatasetType,
        export_profile: ExportProfile,
        format: ExportFormat,
        filters: ExportFilters,
        requested_by: UUID,
    ) -> CreateExport:
        return cls(
            dataset_type,
            export_profile,
            format,
            filters,
            requested_by,
            uuid4(),
            datetime.now(UTC),
        )


def category(dataset_type: DatasetType) -> DatasetCategory:
    if dataset_type == DatasetType.ANALYTICAL_OCCUPANCY:
        return DatasetCategory.ANALYTICAL
    return DatasetCategory.OPERATIONAL


def recovery_failure(*, snapshot_lost: bool) -> FailureCode:
    return FailureCode.SNAPSHOT_LOST if snapshot_lost else FailureCode.ABANDONED_PROCESSING
