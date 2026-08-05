from __future__ import annotations

import csv
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from research.experiments.spec012_weekly_occupancy.baseline import (
    BaselineValidationError,
    Observation,
    PredictionBucket,
    add_temporal_features,
    build_report,
    build_spec012_payload,
    evaluate,
    fit_weekly_baseline,
    load_dataset,
    main,
    predict_holdout,
    validate_non_overlapping_windows,
)

HEADERS = ("bucket_from", "bucket_to", "timezone", "effective_occupancy_rate")


def _rows(*, timezone: str = "UTC", weeks: int = 1) -> list[dict[str, str]]:
    zone = ZoneInfo(timezone)
    monday = datetime(2026, 1, 5, tzinfo=zone)
    result: list[dict[str, str]] = []
    for week in range(weeks):
        for day in range(7):
            for hour in range(24):
                bucket_from = monday + timedelta(weeks=week, days=day, hours=hour)
                result.append(
                    {
                        "bucket_from": bucket_from.astimezone(UTC).isoformat(),
                        "bucket_to": (bucket_from + timedelta(hours=1))
                        .astimezone(UTC)
                        .isoformat(),
                        "timezone": timezone,
                        "effective_occupancy_rate": str((day * 24 + hour) / 167),
                    }
                )
    return result


def _csv(
    path: Path, rows: list[dict[str, str]], headers: tuple[str, ...] = HEADERS
) -> Path:
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.DictWriter(destination, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _observations(rows: list[dict[str, str]]) -> tuple[Observation, ...]:
    return tuple(
        Observation(
            datetime.fromisoformat(row["bucket_from"]).astimezone(UTC),
            datetime.fromisoformat(row["bucket_to"]).astimezone(UTC),
            row["timezone"],
            float(row["effective_occupancy_rate"]),
        )
        for row in rows
    )


def test_valid_dataset_produces_168_canonically_ordered_mean_buckets(
    tmp_path: Path,
) -> None:
    rows = _rows(weeks=2)
    second_monday_08 = 168 + 8
    rows[8]["effective_occupancy_rate"] = "0.2"
    rows[second_monday_08]["effective_occupancy_rate"] = "0.6"
    dataset = load_dataset(_csv(tmp_path / "training.csv", rows), timezone="UTC")

    buckets = fit_weekly_baseline(add_temporal_features(dataset, timezone="UTC"))

    assert len(buckets) == 168
    assert [(item.day_index, item.hour_of_day) for item in buckets] == [
        (day, hour) for day in range(7) for hour in range(24)
    ]
    assert buckets[8].expected_occupancy_rate == pytest.approx(0.4)


def test_temporal_features_use_facility_timezone() -> None:
    absolute = datetime(2026, 1, 5, 2, tzinfo=UTC)
    item = Observation(
        absolute, absolute + timedelta(hours=1), "America/Sao_Paulo", 0.25
    )

    featured = add_temporal_features((item,), timezone="America/Sao_Paulo")[0]

    assert featured.day_index == 6
    assert featured.hour_of_day == 23


def test_evaluation_reports_mae_rmse_and_global_mean_comparison() -> None:
    metrics = evaluate([0.0, 1.0], [0.25, 0.75])
    assert metrics == {"mae": pytest.approx(0.25), "rmse": pytest.approx(0.25)}

    training = _observations(_rows())
    buckets = fit_weekly_baseline(add_temporal_features(training, timezone="UTC"))
    holdout_rows = _rows()
    for row in holdout_rows:
        row["bucket_from"] = (
            datetime.fromisoformat(row["bucket_from"]) + timedelta(weeks=1)
        ).isoformat()
        row["bucket_to"] = (
            datetime.fromisoformat(row["bucket_to"]) + timedelta(weeks=1)
        ).isoformat()
        row["effective_occupancy_rate"] = "0.5"
    report = build_report(
        training,
        buckets,
        holdout=_observations(holdout_rows),
        timezone="UTC",
    )
    expected_global = math.fsum(item.target for item in training) / len(training)
    assert report["weekday_hour_baseline"]["mae"] == pytest.approx(
        math.fsum(abs(item.expected_occupancy_rate - 0.5) for item in buckets) / 168
    )
    assert report["weekday_hour_baseline"]["rmse"] == pytest.approx(
        math.sqrt(
            math.fsum((item.expected_occupancy_rate - 0.5) ** 2 for item in buckets)
            / 168
        )
    )
    assert report["global_mean_baseline"]["prediction"] == pytest.approx(
        expected_global
    )
    assert report["global_mean_baseline"]["mae"] == pytest.approx(
        abs(expected_global - 0.5)
    )


@pytest.mark.parametrize(
    ("headers", "mutate", "message"),
    [
        (("bucket_from", "bucket_to", "timezone"), None, "missing required columns"),
        (HEADERS, ("effective_occupancy_rate", "nan"), "must be finite"),
        (HEADERS, ("effective_occupancy_rate", "1.1"), "must be between 0 and 1"),
    ],
)
def test_invalid_dataset_values_are_rejected(
    tmp_path: Path,
    headers: tuple[str, ...],
    mutate: tuple[str, str] | None,
    message: str,
) -> None:
    rows = _rows()
    if mutate is not None:
        rows[0][mutate[0]] = mutate[1]
    with pytest.raises(BaselineValidationError, match=message):
        load_dataset(_csv(tmp_path / "invalid.csv", rows, headers), timezone="UTC")


def test_missing_weekday_hour_coverage_is_rejected() -> None:
    training = _observations(_rows()[:-1])
    with pytest.raises(BaselineValidationError, match="missing 1 weekday/hour groups"):
        fit_weekly_baseline(add_temporal_features(training, timezone="UTC"))


def test_overlapping_training_and_holdout_are_rejected() -> None:
    observations = _observations(_rows())
    with pytest.raises(BaselineValidationError, match="must not overlap"):
        validate_non_overlapping_windows(observations, observations)


def test_spec012_payload_has_168_unique_valid_buckets() -> None:
    observations = _observations(_rows())
    buckets = fit_weekly_baseline(add_temporal_features(observations, timezone="UTC"))
    facility_id = str(uuid4())
    payload = build_spec012_payload(
        buckets,
        scope_type="FACILITY",
        facility_id=facility_id,
        station_id=None,
        connector_id=None,
        timezone="UTC",
        model_name="weekday-hour-mean",
        model_version="1.0.0",
        external_run_id="test-run",
        generated_at="2026-03-31T00:00:00Z",
        training_data_from="2026-01-05T00:00:00Z",
        training_data_to="2026-01-12T00:00:00Z",
    )

    assert payload["facility_id"] == str(UUID(facility_id))
    assert len(payload["buckets"]) == 168
    assert (
        len({(item["day_of_week"], item["hour_of_day"]) for item in payload["buckets"]})
        == 168
    )
    assert payload["buckets"][0]["day_of_week"] == "MONDAY"
    assert payload["buckets"][-1]["hour_of_day"] == 23
    assert all(0 <= item["expected_occupancy_rate"] <= 1 for item in payload["buckets"])


def test_predict_holdout_uses_matching_weekday_hour() -> None:
    buckets = tuple(
        PredictionBucket(day, hour, (day * 24 + hour) / 167)
        for day in range(7)
        for hour in range(24)
    )
    observations = add_temporal_features(_observations(_rows()), timezone="UTC")
    assert predict_holdout(observations, buckets) == pytest.approx(
        [item.target for item in observations]
    )


def test_cli_writes_prediction_and_evaluation_report(tmp_path: Path) -> None:
    training_path = _csv(tmp_path / "training.csv", _rows())
    holdout_rows = _rows()
    for row in holdout_rows:
        row["bucket_from"] = (
            datetime.fromisoformat(row["bucket_from"]) + timedelta(weeks=1)
        ).isoformat()
        row["bucket_to"] = (
            datetime.fromisoformat(row["bucket_to"]) + timedelta(weeks=1)
        ).isoformat()
    holdout_path = _csv(tmp_path / "holdout.csv", holdout_rows)
    prediction_path = tmp_path / "prediction.json"
    report_path = tmp_path / "report.json"

    result = main(
        [
            "--training",
            str(training_path),
            "--holdout",
            str(holdout_path),
            "--output",
            str(prediction_path),
            "--report",
            str(report_path),
            "--facility-id",
            str(uuid4()),
            "--timezone",
            "UTC",
            "--model-name",
            "weekday-hour-mean",
            "--model-version",
            "1.0.0",
            "--external-run-id",
            "cli-test",
            "--training-data-from",
            "2026-01-05T00:00:00Z",
            "--training-data-to",
            "2026-01-12T00:00:00Z",
            "--generated-at",
            "2026-01-19T00:00:00Z",
        ]
    )

    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert result == 0
    assert len(prediction["buckets"]) == 168
    assert report["training_row_count"] == 168
    assert report["holdout_row_count"] == 168
    assert report["weekday_hour_baseline"]["mae"] == pytest.approx(0)
