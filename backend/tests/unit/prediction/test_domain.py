from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from app.modules.prediction.domain import (
    PredictionBucket,
    PredictionBucketCountError,
    PredictionBucketDuplicateError,
    PredictionRateError,
    PredictionScope,
    PredictionScopeError,
    PredictionScopeType,
    PublicationContent,
    Weekday,
)
from app.modules.prediction.service import PredictionService


def buckets(rate: float = 0.25) -> list[PredictionBucket]:
    return [PredictionBucket(day, hour, rate) for day in Weekday for hour in range(24)]


def content(items: list[PredictionBucket], facility_id: UUID | None = None) -> PublicationContent:
    return PublicationContent.create(
        scope=PredictionScope(
            PredictionScopeType.FACILITY,
            facility_id or uuid4(),
        ),
        timezone="UTC",
        contract_version="1.0",
        model_name="baseline",
        model_version="1.0.0",
        external_run_id="run-1",
        generated_at=datetime(2026, 8, 1, tzinfo=UTC),
        dataset_export_id=None,
        training_data_from=None,
        training_data_to=None,
        buckets=items,
    )


def test_complete_profile_is_canonical_and_order_independent() -> None:
    facility_id = uuid4()
    ordered = content(buckets(), facility_id)
    reversed_profile = content(list(reversed(buckets())), facility_id)

    assert len(ordered.buckets) == 168
    assert ordered.buckets[0].day_of_week == Weekday.MONDAY
    assert ordered.buckets[0].hour_of_day == 0
    assert ordered.buckets[-1].day_of_week == Weekday.SUNDAY
    assert ordered.buckets[-1].hour_of_day == 23
    assert ordered.canonical_json == reversed_profile.canonical_json
    assert ordered.sha256 == reversed_profile.sha256


def test_profile_rejects_wrong_count_duplicates_and_invalid_rates() -> None:
    with pytest.raises(PredictionBucketCountError):
        content(buckets()[:-1])

    duplicate = buckets()
    duplicate[-1] = duplicate[0]
    with pytest.raises(PredictionBucketDuplicateError):
        content(duplicate)

    for invalid in (-0.01, 1.01, float("nan"), float("inf"), float("-inf")):
        invalid_profile = buckets()
        invalid_profile[0] = PredictionBucket(Weekday.MONDAY, 0, invalid)
        with pytest.raises(PredictionRateError):
            content(invalid_profile)


def test_profile_rejects_extra_bucket_invalid_hours_and_non_numeric_values() -> None:
    with pytest.raises(PredictionBucketCountError):
        content(buckets() + [PredictionBucket(Weekday.MONDAY, 0, 0.5)])

    for hour in (-1, 24, True):
        profile = buckets()
        profile[0] = PredictionBucket(Weekday.MONDAY, hour, 0.5)
        with pytest.raises(ValueError):
            content(profile)

    for rate in (True, "0.5"):
        profile = buckets()
        profile[0] = PredictionBucket(Weekday.MONDAY, 0, rate)  # type: ignore[arg-type]
        with pytest.raises(PredictionRateError):
            content(profile)


@pytest.mark.parametrize(
    ("scope_type", "station", "connector"),
    [
        (PredictionScopeType.FACILITY, uuid4(), None),
        (PredictionScopeType.FACILITY, None, uuid4()),
        (PredictionScopeType.STATION, None, None),
        (PredictionScopeType.STATION, uuid4(), uuid4()),
        (PredictionScopeType.CONNECTOR, None, uuid4()),
        (PredictionScopeType.CONNECTOR, uuid4(), None),
    ],
)
def test_scope_shape_is_exact(
    scope_type: PredictionScopeType, station: object, connector: object
) -> None:
    with pytest.raises(PredictionScopeError):
        PredictionScope(
            scope_type,
            uuid4(),
            station,  # type: ignore[arg-type]
            connector,  # type: ignore[arg-type]
        ).validate()


def test_metadata_requires_explicit_offsets_and_complete_training_window() -> None:
    with pytest.raises(ValueError, match="explicit timezone"):
        PublicationContent.create(
            scope=PredictionScope(PredictionScopeType.FACILITY, uuid4()),
            timezone="UTC",
            contract_version="1.0",
            model_name="baseline",
            model_version="1",
            external_run_id="run",
            generated_at=datetime(2026, 8, 1),
            dataset_export_id=None,
            training_data_from=None,
            training_data_to=None,
            buckets=buckets(),
        )

    with pytest.raises(ValueError, match="boundaries"):
        PublicationContent.create(
            scope=PredictionScope(PredictionScopeType.FACILITY, uuid4()),
            timezone="UTC",
            contract_version="1.0",
            model_name="baseline",
            model_version="1",
            external_run_id="run",
            generated_at=datetime(2026, 8, 1, tzinfo=UTC),
            dataset_export_id=None,
            training_data_from=datetime(2026, 7, 1, tzinfo=UTC),
            training_data_to=None,
            buckets=buckets(),
        )


def test_timestamp_lookup_uses_facility_local_time_and_dst_offset() -> None:
    spring_day, spring_hour = PredictionService.resolve_time(
        timezone="America/New_York",
        day_of_week=None,
        hour_of_day=None,
        requested_timestamp=datetime.fromisoformat("2026-03-08T07:30:00+00:00"),
    )
    repeated_first = PredictionService.resolve_time(
        timezone="America/New_York",
        day_of_week=None,
        hour_of_day=None,
        requested_timestamp=datetime.fromisoformat("2026-11-01T05:30:00+00:00"),
    )
    repeated_second = PredictionService.resolve_time(
        timezone="America/New_York",
        day_of_week=None,
        hour_of_day=None,
        requested_timestamp=datetime.fromisoformat("2026-11-01T06:30:00+00:00"),
    )

    assert (spring_day, spring_hour) == (Weekday.SUNDAY, 3)
    assert repeated_first == repeated_second == (Weekday.SUNDAY, 1)


def test_point_time_inputs_are_exclusive_and_require_explicit_offset() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        PredictionService.resolve_time(
            timezone="UTC",
            day_of_week=Weekday.MONDAY,
            hour_of_day=8,
            requested_timestamp=datetime(2026, 8, 3, tzinfo=UTC),
        )
    with pytest.raises(ValueError, match="explicit timezone"):
        PredictionService.resolve_time(
            timezone="UTC",
            day_of_week=None,
            hour_of_day=None,
            requested_timestamp=datetime(2026, 8, 3, 8),
        )
