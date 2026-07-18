from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.modules.analytics.application.models import Granularity
from app.modules.analytics.projections.smart_charging.calculations import (
    buckets,
    clipped_minutes,
    operating_intervals,
    ratio,
    reservation_metrics,
    session_metrics,
)


@dataclass
class Record:
    id: UUID
    status: str
    start_at: datetime
    end_at: datetime
    reservation_id: UUID | None = None
    started_at: datetime | None = None


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_rate_and_reservation_denominators() -> None:
    fulfilled = Record(uuid4(), "COMPLETED", dt("2026-01-01T10:00Z"), dt("2026-01-01T11:00Z"))
    no_show = Record(uuid4(), "NO_SHOW", dt("2026-01-01T12:00Z"), dt("2026-01-01T13:00Z"))
    cancelled = Record(uuid4(), "CANCELLED", dt("2026-01-01T14:00Z"), dt("2026-01-01T15:00Z"))
    session = Record(uuid4(), "COMPLETED", fulfilled.start_at, fulfilled.end_at, fulfilled.id)
    metrics = reservation_metrics(
        [fulfilled, no_show, cancelled], {fulfilled.id: session}, [60, 60, 60]
    )
    assert metrics["reservation_fulfillment_rate"] == 0.5
    assert metrics["no_show_rate"] == 0.5
    assert metrics["cancellation_rate"] == pytest.approx(1 / 3, abs=0.000001)
    assert ratio(0, 0) is None


def test_confirmed_reservation_without_session_is_pending() -> None:
    reservation = Record(uuid4(), "CONFIRMED", dt("2026-01-01T10:00Z"), dt("2026-01-01T11:00Z"))

    metrics = reservation_metrics([reservation], {}, [60])

    assert metrics["fulfilled_reservations"] == 0
    assert metrics["pending_reservations"] == 1


@pytest.mark.parametrize("session_status", ["ACTIVE", "COMPLETED"])
def test_confirmed_reservation_with_session_is_fulfilled_not_pending(
    session_status: str,
) -> None:
    reservation = Record(uuid4(), "CONFIRMED", dt("2026-01-01T10:00Z"), dt("2026-01-01T11:00Z"))
    session = Record(
        uuid4(), session_status, reservation.start_at, reservation.end_at, reservation.id
    )

    metrics = reservation_metrics([reservation], {reservation.id: session}, [60])

    assert metrics["fulfilled_reservations"] == 1
    assert metrics["pending_reservations"] == 0
    assert not (metrics["fulfilled_reservations"] and metrics["pending_reservations"])


def test_session_delay_includes_early_start_and_on_time_boundaries() -> None:
    reservation = Record(uuid4(), "ACTIVE", dt("2026-01-01T10:00Z"), dt("2026-01-01T11:00Z"))
    session = Record(
        uuid4(),
        "ACTIVE",
        reservation.start_at,
        reservation.end_at,
        reservation.id,
        dt("2026-01-01T09:45Z"),
    )
    metrics = session_metrics([session], {reservation.id: reservation}, [60])
    assert metrics["average_session_start_delay_minutes"] == -15
    assert metrics["on_time_start_rate"] == 1


def test_operating_hours_clip_and_capacity() -> None:
    window = (dt("2026-07-06T00:00Z"), dt("2026-07-07T00:00Z"))
    intervals = operating_intervals(
        *window, "UTC", {"monday": {"opens": "08:00", "closes": "18:00"}}
    )
    assert clipped_minutes(*window, intervals) == 600
    assert clipped_minutes(dt("2026-07-06T17:00Z"), dt("2026-07-06T19:00Z"), intervals) == 60


def test_dst_daily_buckets_and_partial_edges() -> None:
    result = buckets(
        dt("2026-03-08T06:30Z"), dt("2026-03-09T05:00Z"), "America/New_York", Granularity.DAY
    )
    assert len(result) == 2
    assert result[0][0].isoformat() == "2026-03-08T01:30:00-05:00"
    assert result[0][1].isoformat() == "2026-03-09T00:00:00-04:00"


def test_dst_fallback_preserves_both_repeated_hour_buckets() -> None:
    window_start = dt("2026-11-01T04:00Z")
    window_end = dt("2026-11-01T08:00Z")

    result = buckets(window_start, window_end, "America/New_York", Granularity.HOUR)
    absolute_intervals = [(left.astimezone(UTC), right.astimezone(UTC)) for left, right in result]
    repeated_hours = [interval for interval in result if interval[0].hour == 1]

    assert len(result) == 4
    assert len(repeated_hours) == 2
    assert [interval[0].utcoffset() for interval in repeated_hours] == [
        timedelta(hours=-4),
        timedelta(hours=-5),
    ]
    assert [interval[0].fold for interval in repeated_hours] == [0, 1]
    assert [interval[0].astimezone(UTC) for interval in repeated_hours] == [
        dt("2026-11-01T05:00Z"),
        dt("2026-11-01T06:00Z"),
    ]
    assert all(right - left == timedelta(hours=1) for left, right in absolute_intervals)
    assert all(
        absolute_intervals[index][1] == absolute_intervals[index + 1][0]
        for index in range(len(absolute_intervals) - 1)
    )
    assert (
        sum((right - left for left, right in absolute_intervals), timedelta())
        == window_end - window_start
    )


@pytest.mark.parametrize("granularity", list(Granularity))
def test_all_granularities_are_ordered(granularity: Granularity) -> None:
    result = buckets(
        datetime(2026, 1, 15, tzinfo=UTC), datetime(2026, 3, 2, tzinfo=UTC), "UTC", granularity
    )
    assert result
    assert all(left < right for left, right in result)
    assert all(result[index][1] == result[index + 1][0] for index in range(len(result) - 1))
