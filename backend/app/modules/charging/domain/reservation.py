from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from uuid import UUID, uuid4

MINIMUM_DURATION = timedelta(minutes=15)
MAXIMUM_DURATION = timedelta(hours=24)
EARLY_START = timedelta(minutes=15)
GRACE_PERIOD = timedelta(minutes=15)
CANCELLATION_CUTOFF = timedelta(minutes=60)


class ReservationStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    LATE_CANCELLED = "LATE_CANCELLED"
    NO_SHOW = "NO_SHOW"


BLOCKING_STATUSES = (ReservationStatus.CONFIRMED, ReservationStatus.ACTIVE)


def normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must include an explicit timezone offset")
    return value.astimezone(UTC)


def validate_interval(
    start_at: datetime, end_at: datetime, *, now: datetime
) -> tuple[datetime, datetime]:
    start = normalize_utc(start_at)
    end = normalize_utc(end_at)
    current = normalize_utc(now)
    if start >= end:
        raise ValueError("start_at must be earlier than end_at")
    duration = end - start
    if duration < MINIMUM_DURATION or duration > MAXIMUM_DURATION:
        raise ValueError("duration must be between 15 minutes and 24 hours")
    if start < current:
        raise ValueError("start_at must not be in the past")
    return start, end


@dataclass(frozen=True)
class Reservation:
    id: UUID
    owner_id: UUID
    vehicle_id: UUID
    connector_id: UUID
    start_at: datetime
    end_at: datetime
    status: ReservationStatus
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    late_cancelled_at: datetime | None = None
    no_show_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        owner_id: UUID,
        vehicle_id: UUID,
        connector_id: UUID,
        start_at: datetime,
        end_at: datetime,
        now: datetime,
    ) -> Reservation:
        current = normalize_utc(now)
        start, end = validate_interval(start_at, end_at, now=current)
        return cls(
            uuid4(),
            owner_id,
            vehicle_id,
            connector_id,
            start,
            end,
            ReservationStatus.CONFIRMED,
            current,
            current,
        )

    def reschedule(
        self, *, vehicle_id: UUID, start_at: datetime, end_at: datetime, now: datetime
    ) -> Reservation:
        current = normalize_utc(now)
        if self.status != ReservationStatus.CONFIRMED:
            raise ValueError("only CONFIRMED reservations may be rescheduled")
        if current >= self.start_at - EARLY_START:
            raise ValueError("reservation cannot be rescheduled after the Early Start window opens")
        start, end = validate_interval(start_at, end_at, now=current)
        return replace(self, vehicle_id=vehicle_id, start_at=start, end_at=end, updated_at=current)

    def cancel(self, *, now: datetime) -> Reservation:
        current = normalize_utc(now)
        if self.status != ReservationStatus.CONFIRMED:
            raise ValueError("only CONFIRMED reservations may be cancelled")
        if current > self.start_at + GRACE_PERIOD:
            raise ValueError("overdue reservation must be marked NO_SHOW")
        if current <= self.start_at - CANCELLATION_CUTOFF:
            return replace(
                self, status=ReservationStatus.CANCELLED, cancelled_at=current, updated_at=current
            )
        return replace(
            self,
            status=ReservationStatus.LATE_CANCELLED,
            late_cancelled_at=current,
            updated_at=current,
        )

    def activate(
        self,
        *,
        now: datetime,
        connector_operational: bool = True,
        connector_available: bool = True,
        active_session_exists: bool = False,
    ) -> Reservation:
        current = normalize_utc(now)
        if self.status != ReservationStatus.CONFIRMED:
            raise ValueError("only CONFIRMED reservations may be activated")
        if not self.start_at - EARLY_START <= current <= self.start_at + GRACE_PERIOD:
            raise ValueError("reservation is outside its activation window")
        if not connector_operational or not connector_available or active_session_exists:
            raise ValueError("connector is unavailable for activation")
        return replace(
            self, status=ReservationStatus.ACTIVE, activated_at=current, updated_at=current
        )

    def complete(self, *, now: datetime) -> Reservation:
        current = normalize_utc(now)
        if self.status != ReservationStatus.ACTIVE:
            raise ValueError("only ACTIVE reservations may be completed")
        return replace(
            self, status=ReservationStatus.COMPLETED, completed_at=current, updated_at=current
        )

    def mark_no_show(self, *, now: datetime) -> Reservation:
        current = normalize_utc(now)
        if self.status != ReservationStatus.CONFIRMED:
            raise ValueError("only CONFIRMED reservations may become NO_SHOW")
        if current <= self.start_at + GRACE_PERIOD:
            raise ValueError("reservation grace period has not expired")
        return replace(
            self, status=ReservationStatus.NO_SHOW, no_show_at=current, updated_at=current
        )
