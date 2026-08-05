from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TARGET = "effective_occupancy_rate"
WEEKDAYS = (
    "MONDAY",
    "TUESDAY",
    "WEDNESDAY",
    "THURSDAY",
    "FRIDAY",
    "SATURDAY",
    "SUNDAY",
)
REQUIRED_COLUMNS = frozenset({"bucket_from", "bucket_to", "timezone", TARGET})
ScopeType = Literal["FACILITY", "STATION", "CONNECTOR"]
BucketKey = tuple[int, int]


class BaselineValidationError(ValueError):
    """Raised when an input cannot produce a trustworthy SPEC-012 profile."""


@dataclass(frozen=True, slots=True)
class Observation:
    bucket_from: datetime
    bucket_to: datetime
    timezone: str
    target: float


@dataclass(frozen=True, slots=True)
class TemporalObservation:
    bucket_from: datetime
    bucket_to: datetime
    day_index: int
    hour_of_day: int
    target: float


@dataclass(frozen=True, slots=True)
class PredictionBucket:
    day_index: int
    hour_of_day: int
    expected_occupancy_rate: float

    def as_dict(self) -> dict[str, int | float | str]:
        return {
            "day_of_week": WEEKDAYS[self.day_index],
            "hour_of_day": self.hour_of_day,
            "expected_occupancy_rate": self.expected_occupancy_rate,
        }


def _required_value(row: dict[str, str | None], column: str, row_number: int) -> str:
    value = row.get(column)
    if value is None or not value.strip():
        raise BaselineValidationError(f"row {row_number}: {column} must not be empty")
    return value.strip()


def _parse_timestamp(value: str, column: str, row_number: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BaselineValidationError(
            f"row {row_number}: {column} must be a valid timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BaselineValidationError(
            f"row {row_number}: {column} must include an explicit timezone offset"
        )
    return parsed.astimezone(UTC)


def _zone(timezone: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise BaselineValidationError(
            f"timezone is not a valid IANA timezone: {timezone}"
        ) from exc


def load_dataset(path: Path, *, timezone: str) -> tuple[Observation, ...]:
    """Load and validate one SPEC-011 ANALYTICAL_OCCUPANCY CSV data file."""
    _zone(timezone)
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        columns = frozenset(reader.fieldnames or ())
        missing = sorted(REQUIRED_COLUMNS - columns)
        if missing:
            raise BaselineValidationError(
                f"dataset is missing required columns: {', '.join(missing)}"
            )

        observations: list[Observation] = []
        for row_number, row in enumerate(reader, start=2):
            bucket_from = _parse_timestamp(
                _required_value(row, "bucket_from", row_number),
                "bucket_from",
                row_number,
            )
            bucket_to = _parse_timestamp(
                _required_value(row, "bucket_to", row_number), "bucket_to", row_number
            )
            if bucket_from >= bucket_to:
                raise BaselineValidationError(
                    f"row {row_number}: bucket_from must be earlier than bucket_to"
                )
            row_timezone = _required_value(row, "timezone", row_number)
            if row_timezone != timezone:
                raise BaselineValidationError(
                    f"row {row_number}: dataset timezone {row_timezone!r} does not match "
                    f"requested timezone {timezone!r}"
                )
            raw_target = _required_value(row, TARGET, row_number)
            try:
                target = float(raw_target)
            except ValueError as exc:
                raise BaselineValidationError(
                    f"row {row_number}: {TARGET} must be numeric"
                ) from exc
            if not math.isfinite(target):
                raise BaselineValidationError(
                    f"row {row_number}: {TARGET} must be finite"
                )
            if not 0 <= target <= 1:
                raise BaselineValidationError(
                    f"row {row_number}: {TARGET} must be between 0 and 1"
                )
            observations.append(
                Observation(bucket_from, bucket_to, row_timezone, target)
            )

    if not observations:
        raise BaselineValidationError("dataset must contain at least one row")
    return tuple(observations)


def add_temporal_features(
    observations: Sequence[Observation], *, timezone: str
) -> tuple[TemporalObservation, ...]:
    """Derive Facility-local weekday and hour from each absolute bucket start."""
    zone = _zone(timezone)
    return tuple(
        TemporalObservation(
            bucket_from=item.bucket_from,
            bucket_to=item.bucket_to,
            day_index=item.bucket_from.astimezone(zone).weekday(),
            hour_of_day=item.bucket_from.astimezone(zone).hour,
            target=item.target,
        )
        for item in observations
    )


def fit_weekly_baseline(
    observations: Sequence[TemporalObservation],
) -> tuple[PredictionBucket, ...]:
    """Fit E[effective_occupancy_rate | local weekday, local hour]."""
    grouped: dict[BucketKey, list[float]] = defaultdict(list)
    for item in observations:
        grouped[(item.day_index, item.hour_of_day)].append(item.target)

    expected = {(day, hour) for day in range(7) for hour in range(24)}
    missing = sorted(expected - grouped.keys())
    if missing:
        preview = ", ".join(f"{WEEKDAYS[day]}/{hour:02d}" for day, hour in missing[:8])
        suffix = "..." if len(missing) > 8 else ""
        raise BaselineValidationError(
            f"training dataset is missing {len(missing)} weekday/hour groups: {preview}{suffix}"
        )

    return tuple(
        PredictionBucket(
            day, hour, math.fsum(grouped[(day, hour)]) / len(grouped[(day, hour)])
        )
        for day in range(7)
        for hour in range(24)
    )


def predict_holdout(
    observations: Sequence[TemporalObservation], buckets: Sequence[PredictionBucket]
) -> tuple[float, ...]:
    lookup = {
        (bucket.day_index, bucket.hour_of_day): bucket.expected_occupancy_rate
        for bucket in buckets
    }
    return tuple(lookup[(item.day_index, item.hour_of_day)] for item in observations)


def evaluate(actual: Sequence[float], predicted: Sequence[float]) -> dict[str, float]:
    if not actual or len(actual) != len(predicted):
        raise BaselineValidationError(
            "evaluation requires equally sized non-empty sequences"
        )
    errors = [
        prediction - observed
        for observed, prediction in zip(actual, predicted, strict=True)
    ]
    return {
        "mae": math.fsum(abs(error) for error in errors) / len(errors),
        "rmse": math.sqrt(math.fsum(error * error for error in errors) / len(errors)),
    }


def validate_non_overlapping_windows(
    training: Sequence[Observation], holdout: Sequence[Observation]
) -> None:
    training_from, training_to = dataset_window(training)
    holdout_from, holdout_to = dataset_window(holdout)
    if training_from < holdout_to and holdout_from < training_to:
        raise BaselineValidationError(
            "training and holdout dataset windows must not overlap"
        )


def dataset_window(observations: Sequence[Observation]) -> tuple[datetime, datetime]:
    if not observations:
        raise BaselineValidationError(
            "dataset window requires at least one observation"
        )
    return min(item.bucket_from for item in observations), max(
        item.bucket_to for item in observations
    )


def _explicit_utc(value: str, field: str) -> datetime:
    parsed = _parse_timestamp(value, field, 0)
    return parsed


def _canonical_timestamp(value: datetime) -> str:
    return (
        value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    )


def _uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise BaselineValidationError(f"{field} must be a valid UUID") from exc


def build_spec012_payload(
    buckets: Sequence[PredictionBucket],
    *,
    scope_type: ScopeType,
    facility_id: str,
    station_id: str | None,
    connector_id: str | None,
    timezone: str,
    model_name: str,
    model_version: str,
    external_run_id: str,
    generated_at: str,
    training_data_from: str,
    training_data_to: str,
    dataset_export_id: str | None = None,
) -> dict[str, Any]:
    if (
        len(buckets) != 168
        or len({(bucket.day_index, bucket.hour_of_day) for bucket in buckets}) != 168
    ):
        raise BaselineValidationError(
            "SPEC-012 payload requires 168 unique weekday/hour buckets"
        )
    _zone(timezone)
    if scope_type == "FACILITY" and (
        station_id is not None or connector_id is not None
    ):
        raise BaselineValidationError(
            "FACILITY scope must not include station_id or connector_id"
        )
    if scope_type == "STATION" and (station_id is None or connector_id is not None):
        raise BaselineValidationError(
            "STATION scope requires station_id and excludes connector_id"
        )
    if scope_type == "CONNECTOR" and (station_id is None or connector_id is None):
        raise BaselineValidationError(
            "CONNECTOR scope requires station_id and connector_id"
        )

    generated = _explicit_utc(generated_at, "generated_at")
    training_from = _explicit_utc(training_data_from, "training_data_from")
    training_to = _explicit_utc(training_data_to, "training_data_to")
    if training_from >= training_to:
        raise BaselineValidationError(
            "training_data_from must be earlier than training_data_to"
        )
    if (
        not model_name.strip()
        or not model_version.strip()
        or not external_run_id.strip()
    ):
        raise BaselineValidationError(
            "model and external-run metadata must not be empty"
        )

    payload: dict[str, Any] = {
        "contract_version": "1.0",
        "prediction_type": "WEEKLY_OCCUPANCY",
        "scope_type": scope_type,
        "facility_id": _uuid(facility_id, "facility_id"),
        "timezone": timezone,
        "model_name": model_name.strip(),
        "model_version": model_version.strip(),
        "external_run_id": external_run_id.strip(),
        "generated_at": _canonical_timestamp(generated),
        "training_data_from": _canonical_timestamp(training_from),
        "training_data_to": _canonical_timestamp(training_to),
        "buckets": [bucket.as_dict() for bucket in buckets],
    }
    if station_id is not None:
        payload["station_id"] = _uuid(station_id, "station_id")
    if connector_id is not None:
        payload["connector_id"] = _uuid(connector_id, "connector_id")
    if dataset_export_id is not None:
        payload["dataset_export_id"] = _uuid(dataset_export_id, "dataset_export_id")
    return payload


def build_report(
    training: Sequence[Observation],
    buckets: Sequence[PredictionBucket],
    *,
    holdout: Sequence[Observation] | None = None,
    timezone: str,
) -> dict[str, Any]:
    training_targets = [item.target for item in training]
    bucket_predictions = [item.expected_occupancy_rate for item in buckets]
    global_mean = math.fsum(training_targets) / len(training_targets)
    report: dict[str, Any] = {
        "target": TARGET,
        "features": ["facility_local_weekday", "facility_local_hour_of_day"],
        "technique": "ARITHMETIC_MEAN_BY_WEEKDAY_HOUR",
        "timezone": timezone,
        "training_row_count": len(training),
        "holdout_row_count": len(holdout) if holdout is not None else 0,
        "bucket_count": len(buckets),
        "target_mean": global_mean,
        "prediction_mean": math.fsum(bucket_predictions) / len(bucket_predictions),
        "prediction_min": min(bucket_predictions),
        "prediction_max": max(bucket_predictions),
        "weekday_hour_baseline": None,
        "global_mean_baseline": {"prediction": global_mean, "mae": None, "rmse": None},
    }
    if holdout is not None:
        temporal_holdout = add_temporal_features(holdout, timezone=timezone)
        actual = [item.target for item in temporal_holdout]
        report["weekday_hour_baseline"] = evaluate(
            actual, predict_holdout(temporal_holdout, buckets)
        )
        report["global_mean_baseline"] = {
            "prediction": global_mean,
            **evaluate(actual, [global_mean] * len(actual)),
        }
    return report


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Fit and evaluate the external SPEC-012 weekday/hour occupancy baseline."
    )
    result.add_argument("--training", required=True, type=Path)
    result.add_argument("--holdout", type=Path)
    result.add_argument("--output", required=True, type=Path)
    result.add_argument("--report", type=Path)
    result.add_argument(
        "--scope-type", choices=("FACILITY", "STATION", "CONNECTOR"), default="FACILITY"
    )
    result.add_argument("--facility-id", required=True)
    result.add_argument("--station-id")
    result.add_argument("--connector-id")
    result.add_argument("--timezone", required=True)
    result.add_argument("--model-name", required=True)
    result.add_argument("--model-version", required=True)
    result.add_argument("--external-run-id", required=True)
    result.add_argument("--dataset-export-id")
    result.add_argument("--training-data-from", required=True)
    result.add_argument("--training-data-to", required=True)
    result.add_argument("--generated-at", required=True)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        training = load_dataset(arguments.training, timezone=arguments.timezone)
        temporal_training = add_temporal_features(training, timezone=arguments.timezone)
        buckets = fit_weekly_baseline(temporal_training)
        actual_from, actual_to = dataset_window(training)
        declared_from = _explicit_utc(
            arguments.training_data_from, "training_data_from"
        )
        declared_to = _explicit_utc(arguments.training_data_to, "training_data_to")
        if actual_from < declared_from or actual_to > declared_to:
            raise BaselineValidationError(
                "training rows must be contained in the declared training-data window"
            )

        holdout = None
        if arguments.holdout is not None:
            holdout = load_dataset(arguments.holdout, timezone=arguments.timezone)
            validate_non_overlapping_windows(training, holdout)

        payload = build_spec012_payload(
            buckets,
            scope_type=arguments.scope_type,
            facility_id=arguments.facility_id,
            station_id=arguments.station_id,
            connector_id=arguments.connector_id,
            timezone=arguments.timezone,
            model_name=arguments.model_name,
            model_version=arguments.model_version,
            external_run_id=arguments.external_run_id,
            generated_at=arguments.generated_at,
            training_data_from=arguments.training_data_from,
            training_data_to=arguments.training_data_to,
            dataset_export_id=arguments.dataset_export_id,
        )
        _write_json(arguments.output, payload)
        report = build_report(
            training, buckets, holdout=holdout, timezone=arguments.timezone
        )
        if arguments.report is not None:
            _write_json(arguments.report, report)
        print(json.dumps(report, indent=2))
    except (BaselineValidationError, OSError) as exc:
        parser().error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
