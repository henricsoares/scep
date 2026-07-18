from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.modules.analytics.application.models import Granularity, Metrics

FINAL_RESERVED_STATUSES = {"CONFIRMED", "ACTIVE", "COMPLETED", "NO_SHOW"}
WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


def utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def overlap(
    start: datetime, end: datetime, low: datetime, high: datetime
) -> tuple[datetime, datetime] | None:
    left, right = max(utc(start), utc(low)), min(utc(end), utc(high))
    return (left, right) if left < right else None


def operating_intervals(
    window_from: datetime, window_to: datetime, timezone: str, hours: dict[str, Any] | None
) -> list[tuple[datetime, datetime]]:
    if not hours:
        return [(utc(window_from), utc(window_to))]
    zone = ZoneInfo(timezone)
    first = utc(window_from).astimezone(zone).date() - timedelta(days=1)
    last = utc(window_to).astimezone(zone).date()
    result: list[tuple[datetime, datetime]] = []
    current = first
    while current <= last:
        rule = hours.get(WEEKDAYS[current.weekday()])
        rules = rule if isinstance(rule, list) else [rule]
        for item in rules:
            if not isinstance(item, dict) or not item.get("opens") or not item.get("closes"):
                continue
            opens = time.fromisoformat(str(item["opens"]))
            closes = time.fromisoformat(str(item["closes"]))
            start = datetime.combine(current, opens, zone)
            end_date = current + timedelta(days=1) if closes <= opens else current
            end = datetime.combine(end_date, closes, zone)
            clipped = overlap(start, end, window_from, window_to)
            if clipped:
                result.append(clipped)
        current += timedelta(days=1)
    return result


def clipped_minutes(
    start: datetime, end: datetime, operating: Iterable[tuple[datetime, datetime]]
) -> float:
    seconds = 0.0
    for low, high in operating:
        item = overlap(start, end, low, high)
        if item:
            seconds += (item[1] - item[0]).total_seconds()
    return seconds / 60


def ratio(numerator: float | int, denominator: float | int) -> float | None:
    return None if denominator == 0 else round(numerator / denominator, 6)


def reservation_metrics(
    reservations: list[Any], sessions_by_reservation: dict[Any, Any], durations: list[float]
) -> Metrics:
    total = len(reservations)
    fulfilled = sum(item.id in sessions_by_reservation for item in reservations)
    cancelled = sum(item.status == "CANCELLED" for item in reservations)
    late = sum(item.status == "LATE_CANCELLED" for item in reservations)
    no_show = sum(item.status == "NO_SHOW" for item in reservations)
    active_ids = {
        item.reservation_id for item in sessions_by_reservation.values() if item.status == "ACTIVE"
    }
    pending = sum(item.status == "CONFIRMED" and item.id not in active_ids for item in reservations)
    eligible = fulfilled + no_show
    positive = [value for value in durations if value > 0]
    return {
        "total_reservations": total,
        "fulfilled_reservations": fulfilled,
        "cancelled_reservations": cancelled,
        "late_cancelled_reservations": late,
        "no_show_reservations": no_show,
        "pending_reservations": pending,
        "reservation_fulfillment_rate": ratio(fulfilled, eligible),
        "cancellation_rate": ratio(cancelled, total),
        "late_cancellation_rate": ratio(late, total),
        "no_show_rate": ratio(no_show, eligible),
        "average_reservation_duration_minutes": (
            round(sum(positive) / len(positive), 6) if positive else None
        ),
    }


def session_metrics(
    sessions: list[Any], reservations_by_id: dict[Any, Any], durations: list[float]
) -> Metrics:
    total = len(sessions)
    positive = [value for value in durations if value > 0]
    delays = [
        (
            utc(item.started_at) - utc(reservations_by_id[item.reservation_id].start_at)
        ).total_seconds()
        / 60
        for item in sessions
        if item.reservation_id in reservations_by_id
    ]
    on_time = sum(-15 <= delay <= 15 for delay in delays)
    return {
        "total_charging_sessions": total,
        "active_charging_sessions": sum(item.status == "ACTIVE" for item in sessions),
        "completed_charging_sessions": sum(item.status == "COMPLETED" for item in sessions),
        "average_session_duration_minutes": (
            round(sum(positive) / len(positive), 6) if positive else None
        ),
        "average_session_start_delay_minutes": (
            round(sum(delays) / len(delays), 6) if delays else None
        ),
        "on_time_start_rate": ratio(on_time, total),
    }


def buckets(
    start: datetime, end: datetime, timezone: str, granularity: Granularity
) -> list[tuple[datetime, datetime]]:
    zone = ZoneInfo(timezone)
    local_start, local_end = utc(start).astimezone(zone), utc(end).astimezone(zone)
    if granularity == Granularity.HOUR:
        boundary = local_start.replace(minute=0, second=0, microsecond=0)
    elif granularity == Granularity.DAY:
        boundary = local_start.replace(hour=0, minute=0, second=0, microsecond=0)
    elif granularity == Granularity.WEEK:
        boundary = (local_start - timedelta(days=local_start.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        boundary = local_start.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result: list[tuple[datetime, datetime]] = []
    while boundary < local_end:
        if granularity == Granularity.HOUR:
            following = (boundary.astimezone(UTC) + timedelta(hours=1)).astimezone(zone)
        elif granularity == Granularity.DAY:
            following = datetime.combine(boundary.date() + timedelta(days=1), time(), zone)
        elif granularity == Granularity.WEEK:
            following = datetime.combine(boundary.date() + timedelta(days=7), time(), zone)
        else:
            year, month = (
                (boundary.year + 1, 1)
                if boundary.month == 12
                else (boundary.year, boundary.month + 1)
            )
            following = datetime(year, month, 1, tzinfo=zone)
        left, right = max(local_start, boundary), min(local_end, following)
        if left < right:
            result.append((left, right))
        boundary = following
    return result
