from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.modules.charging.domain.reservation import Reservation, ReservationStatus

NOW = datetime(2026, 7, 13, 12, tzinfo=UTC)


def reservation(*, start: datetime | None = None, end: datetime | None = None) -> Reservation:
    start = start or NOW + timedelta(hours=2)
    return Reservation.create(
        owner_id=uuid4(),
        vehicle_id=uuid4(),
        connector_id=uuid4(),
        start_at=start,
        end_at=end or start + timedelta(hours=1),
        now=NOW,
    )


def test_create_confirmed_and_normalize_offset() -> None:
    item = Reservation.create(
        owner_id=uuid4(),
        vehicle_id=uuid4(),
        connector_id=uuid4(),
        start_at=datetime.fromisoformat("2026-07-13T10:00:00-03:00"),
        end_at=datetime.fromisoformat("2026-07-13T11:00:00-03:00"),
        now=NOW,
    )
    assert item.status == ReservationStatus.CONFIRMED
    assert item.start_at == datetime(2026, 7, 13, 13, tzinfo=UTC)


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (NOW, NOW, "earlier"),
        (NOW + timedelta(hours=1), NOW + timedelta(hours=1, minutes=14), "duration"),
        (NOW + timedelta(hours=1), NOW + timedelta(hours=25, minutes=1), "duration"),
        (NOW - timedelta(seconds=1), NOW + timedelta(hours=1), "past"),
    ],
)
def test_invalid_intervals(start: datetime, end: datetime, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        reservation(start=start, end=end)


def test_duration_boundaries_are_inclusive() -> None:
    start = NOW + timedelta(hours=1)
    assert reservation(start=start, end=start + timedelta(minutes=15))
    assert reservation(start=start, end=start + timedelta(hours=24))


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="offset"):
        reservation(start=datetime(2026, 7, 13, 14), end=datetime(2026, 7, 13, 15))


@pytest.mark.parametrize(
    "activation_time",
    [
        NOW + timedelta(hours=1, minutes=45),
        NOW + timedelta(hours=2),
        NOW + timedelta(hours=2, minutes=15),
    ],
)
def test_activation_window_boundaries(activation_time: datetime) -> None:
    item = reservation().activate(now=activation_time)
    assert item.status == ReservationStatus.ACTIVE
    assert item.end_at == NOW + timedelta(hours=3)


@pytest.mark.parametrize(
    "activation_time",
    [
        NOW + timedelta(hours=1, minutes=44, seconds=59),
        NOW + timedelta(hours=2, minutes=15, seconds=1),
    ],
)
def test_activation_outside_window_is_rejected(activation_time: datetime) -> None:
    with pytest.raises(ValueError, match="activation window"):
        reservation().activate(now=activation_time)


def test_activation_connector_invariants() -> None:
    for kwargs in (
        {"connector_operational": False},
        {"connector_available": False},
        {"active_session_exists": True},
    ):
        with pytest.raises(ValueError, match="unavailable"):
            reservation().activate(now=NOW + timedelta(hours=2), **kwargs)


def test_completion_only_from_active() -> None:
    item = reservation()
    with pytest.raises(ValueError, match="ACTIVE"):
        item.complete(now=NOW + timedelta(hours=3))
    completed = item.activate(now=NOW + timedelta(hours=2)).complete(now=NOW + timedelta(hours=3))
    assert completed.status == ReservationStatus.COMPLETED
    assert completed.completed_at == NOW + timedelta(hours=3)


def test_cancellation_cutoff_and_late_cancellation() -> None:
    item = reservation()
    normal = item.cancel(now=item.start_at - timedelta(minutes=60))
    late = item.cancel(now=item.start_at - timedelta(minutes=60) + timedelta(microseconds=1))
    assert normal.status == ReservationStatus.CANCELLED
    assert normal.cancelled_at is not None
    assert late.status == ReservationStatus.LATE_CANCELLED
    assert late.late_cancelled_at is not None


def test_no_show_strict_grace_boundary() -> None:
    item = reservation()
    with pytest.raises(ValueError, match="not expired"):
        item.mark_no_show(now=item.start_at + timedelta(minutes=15))
    no_show = item.mark_no_show(now=item.start_at + timedelta(minutes=15, microseconds=1))
    assert no_show.status == ReservationStatus.NO_SHOW


@pytest.mark.parametrize(
    "terminal",
    [
        ReservationStatus.COMPLETED,
        ReservationStatus.CANCELLED,
        ReservationStatus.LATE_CANCELLED,
        ReservationStatus.NO_SHOW,
    ],
)
def test_terminal_states_reject_transitions(terminal: ReservationStatus) -> None:
    item = reservation()
    item = item.__class__(**(item.__dict__ | {"status": terminal}))
    with pytest.raises(ValueError):
        item.cancel(now=NOW)
    with pytest.raises(ValueError):
        item.activate(now=item.start_at)


def test_rescheduling_before_early_start_preserves_immutable_fields() -> None:
    item = reservation()
    vehicle_id = uuid4()
    updated = item.reschedule(
        vehicle_id=vehicle_id,
        start_at=item.start_at + timedelta(hours=1),
        end_at=item.end_at + timedelta(hours=1),
        now=item.start_at - timedelta(minutes=15, seconds=1),
    )
    assert updated.vehicle_id == vehicle_id
    assert updated.id == item.id
    assert updated.owner_id == item.owner_id
    assert updated.connector_id == item.connector_id
    assert updated.created_at == item.created_at
    with pytest.raises(ValueError, match="Early Start"):
        item.reschedule(
            vehicle_id=vehicle_id,
            start_at=item.start_at + timedelta(hours=1),
            end_at=item.end_at + timedelta(hours=1),
            now=item.start_at - timedelta(minutes=15),
        )
