from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class PredictionType(StrEnum):
    WEEKLY_OCCUPANCY = "WEEKLY_OCCUPANCY"


class PredictionCycle(StrEnum):
    WEEKLY = "WEEKLY"


class PredictionGranularity(StrEnum):
    HOUR = "HOUR"


class PredictionScopeType(StrEnum):
    FACILITY = "FACILITY"
    STATION = "STATION"
    CONNECTOR = "CONNECTOR"


class Weekday(StrEnum):
    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


WEEKDAYS = tuple(Weekday)
WEEKDAY_INDEX = {day: index for index, day in enumerate(WEEKDAYS)}
EXPECTED_BUCKET_COUNT = 168
CONTRACT_VERSION = "1.0"


class PredictionError(ValueError):
    code = "PREDICTION_INVALID"
    status_code = 400


class PredictionSchemaError(PredictionError):
    status_code = 422


class PredictionBucketCountError(PredictionSchemaError):
    code = "PREDICTION_BUCKET_COUNT_INVALID"


class PredictionBucketMissingError(PredictionSchemaError):
    code = "PREDICTION_BUCKET_MISSING"


class PredictionBucketDuplicateError(PredictionSchemaError):
    code = "PREDICTION_BUCKET_DUPLICATE"


class PredictionRateError(PredictionSchemaError):
    code = "PREDICTION_RATE_INVALID"


class PredictionScopeError(PredictionError):
    code = "PREDICTION_SCOPE_INVALID"


class PredictionHierarchyError(PredictionError):
    code = "PREDICTION_HIERARCHY_MISMATCH"


class PredictionTimezoneError(PredictionError):
    code = "PREDICTION_TIMEZONE_MISMATCH"


class PredictionScopeIneligibleError(PredictionError):
    code = "PREDICTION_SCOPE_INELIGIBLE"


class PredictionDatasetExportError(PredictionError):
    code = "PREDICTION_DATASET_EXPORT_INVALID"


class PredictionIdempotencyConflictError(PredictionError):
    code = "PREDICTION_IDEMPOTENCY_CONFLICT"
    status_code = 409


class PredictionNotFoundError(PredictionError):
    code = "PREDICTION_NOT_FOUND"
    status_code = 404


class PredictionCurrentNotFoundError(PredictionNotFoundError):
    code = "PREDICTION_CURRENT_NOT_FOUND"


class PredictionAuthorizationError(PredictionError):
    code = "PREDICTION_FORBIDDEN"
    status_code = 403


class PredictionPersistenceError(RuntimeError):
    code = "PREDICTION_PERSISTENCE_FAILURE"
    status_code = 500


@dataclass(frozen=True, slots=True)
class PredictionScope:
    scope_type: PredictionScopeType
    facility_id: UUID
    station_id: UUID | None = None
    connector_id: UUID | None = None

    def validate(self) -> None:
        if self.scope_type == PredictionScopeType.FACILITY:
            valid = self.station_id is None and self.connector_id is None
        elif self.scope_type == PredictionScopeType.STATION:
            valid = self.station_id is not None and self.connector_id is None
        else:
            valid = self.station_id is not None and self.connector_id is not None
        if not valid:
            raise PredictionScopeError("Prediction scope hierarchy is invalid.")

    @property
    def key(self) -> str:
        self.validate()
        values = [self.scope_type.value, str(self.facility_id)]
        if self.station_id is not None:
            values.append(str(self.station_id))
        if self.connector_id is not None:
            values.append(str(self.connector_id))
        return ":".join(values)

    def canonical(self) -> dict[str, str | None]:
        return {
            "scope_type": self.scope_type.value,
            "facility_id": str(self.facility_id),
            "station_id": str(self.station_id) if self.station_id else None,
            "connector_id": str(self.connector_id) if self.connector_id else None,
        }


@dataclass(frozen=True, slots=True)
class PredictionBucket:
    day_of_week: Weekday
    hour_of_day: int
    expected_occupancy_rate: float

    def validate(self) -> None:
        if isinstance(self.hour_of_day, bool) or not isinstance(self.hour_of_day, int):
            raise PredictionSchemaError("hour_of_day must be an integer.")
        if not 0 <= self.hour_of_day <= 23:
            raise PredictionSchemaError("hour_of_day must be between 0 and 23.")
        rate = self.expected_occupancy_rate
        if isinstance(rate, bool) or not isinstance(rate, int | float):
            raise PredictionRateError("expected_occupancy_rate must be a JSON number.")
        if not math.isfinite(float(rate)) or not 0 <= float(rate) <= 1:
            raise PredictionRateError("expected_occupancy_rate must be finite and between 0 and 1.")

    @property
    def sort_key(self) -> tuple[int, int]:
        return WEEKDAY_INDEX[self.day_of_week], self.hour_of_day


def canonical_buckets(buckets: list[PredictionBucket]) -> tuple[PredictionBucket, ...]:
    if len(buckets) != EXPECTED_BUCKET_COUNT:
        raise PredictionBucketCountError("A weekly profile must contain exactly 168 buckets.")
    seen: set[tuple[Weekday, int]] = set()
    for bucket in buckets:
        bucket.validate()
        key = (bucket.day_of_week, bucket.hour_of_day)
        if key in seen:
            raise PredictionBucketDuplicateError("The weekly profile contains a duplicate bucket.")
        seen.add(key)
    expected = {(day, hour) for day in WEEKDAYS for hour in range(24)}
    if seen != expected:
        raise PredictionBucketMissingError("The weekly profile is incomplete.")
    return tuple(sorted(buckets, key=lambda item: item.sort_key))


def canonical_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PredictionSchemaError(
            f"{field} must be non-empty and have no surrounding whitespace."
        )
    normalized = unicodedata.normalize("NFC", value)
    if not normalized:
        raise PredictionSchemaError(f"{field} must be non-empty.")
    return normalized


def utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise PredictionSchemaError(f"{field} must include an explicit timezone offset.")
    return value.astimezone(UTC)


def timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical_rate(value: float) -> int | float:
    number = float(value)
    if number == 0:
        return 0
    if number == 1:
        return 1
    return number


@dataclass(frozen=True, slots=True)
class PublicationContent:
    scope: PredictionScope
    timezone: str
    contract_version: str
    model_name: str
    model_version: str
    external_run_id: str
    generated_at: datetime
    dataset_export_id: UUID | None
    training_data_from: datetime | None
    training_data_to: datetime | None
    buckets: tuple[PredictionBucket, ...]

    @classmethod
    def create(
        cls,
        *,
        scope: PredictionScope,
        timezone: str,
        contract_version: str,
        model_name: str,
        model_version: str,
        external_run_id: str,
        generated_at: datetime,
        dataset_export_id: UUID | None,
        training_data_from: datetime | None,
        training_data_to: datetime | None,
        buckets: list[PredictionBucket],
    ) -> PublicationContent:
        scope.validate()
        if contract_version != CONTRACT_VERSION:
            raise PredictionSchemaError("contract_version must be 1.0.")
        generated = utc(generated_at, "generated_at")
        if (training_data_from is None) != (training_data_to is None):
            raise PredictionError("Both training-data boundaries are required together.")
        training_from = (
            utc(training_data_from, "training_data_from") if training_data_from else None
        )
        training_to = utc(training_data_to, "training_data_to") if training_data_to else None
        if training_from is not None and training_to is not None and training_from >= training_to:
            raise PredictionError("training_data_from must be earlier than training_data_to.")
        return cls(
            scope=scope,
            timezone=canonical_text(timezone, "timezone"),
            contract_version=contract_version,
            model_name=canonical_text(model_name, "model_name"),
            model_version=canonical_text(model_version, "model_version"),
            external_run_id=canonical_text(external_run_id, "external_run_id"),
            generated_at=generated,
            dataset_export_id=dataset_export_id,
            training_data_from=training_from,
            training_data_to=training_to,
            buckets=canonical_buckets(buckets),
        )

    def canonical_object(self) -> dict[str, Any]:
        return {
            "prediction_type": PredictionType.WEEKLY_OCCUPANCY.value,
            "cycle": PredictionCycle.WEEKLY.value,
            "granularity": PredictionGranularity.HOUR.value,
            "contract_version": self.contract_version,
            "scope": self.scope.canonical(),
            "timezone": self.timezone,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "external_run_id": self.external_run_id,
            "generated_at": timestamp(self.generated_at),
            "dataset_export_id": str(self.dataset_export_id) if self.dataset_export_id else None,
            "training_data_from": timestamp(self.training_data_from),
            "training_data_to": timestamp(self.training_data_to),
            "buckets": [
                {
                    "day_of_week": bucket.day_of_week.value,
                    "hour_of_day": bucket.hour_of_day,
                    "expected_occupancy_rate": canonical_rate(bucket.expected_occupancy_rate),
                }
                for bucket in self.buckets
            ],
        }

    @property
    def canonical_json(self) -> str:
        return json.dumps(
            self.canonical_object(),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
        )

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class WeeklyOccupancyPredictionPublication:
    id: UUID
    content: PublicationContent
    accepted_at: datetime
    publisher_subject_id: UUID
    content_sha256: str
    is_current: bool
