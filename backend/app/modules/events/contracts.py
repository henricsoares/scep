from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.events.domain import DomainEvent


def event(
    event_type: str,
    aggregate_id: UUID,
    aggregate_type: str,
    producer_module: str,
    occurred_at: datetime,
    payload: dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
    correlation_id: UUID | None = None,
) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        aggregate_id=aggregate_id,
        aggregate_type=aggregate_type,
        producer_module=producer_module,
        occurred_at=occurred_at,
        payload=payload,
        metadata=metadata or {},
        correlation_id=correlation_id,
    )


def reservation_event(kind: str, item: Any, *, cancellation_type: str | None = None) -> DomainEvent:
    payload = (
        {"cancellation_type": cancellation_type}
        if cancellation_type
        else {
            "owner_id": str(item.owner_id),
            "vehicle_id": str(item.vehicle_id),
            "connector_id": str(item.connector_id),
            "start_at": item.start_at.isoformat(),
            "end_at": item.end_at.isoformat(),
        }
    )
    return event(
        f"reservation.{kind}", item.id, "Reservation", "charging", item.updated_at, payload
    )


def charging_session_event(kind: str, item: Any) -> DomainEvent:
    payload = (
        {"reservation_id": str(item.reservation_id), "ended_at": item.ended_at.isoformat()}
        if kind == "completed"
        else {
            "reservation_id": str(item.reservation_id),
            "owner_id": str(item.owner_id),
            "vehicle_id": str(item.vehicle_id),
            "connector_id": str(item.connector_id),
            "started_at": item.started_at.isoformat(),
        }
    )
    occurred = item.ended_at if kind == "completed" else item.started_at
    return event(
        f"charging-session.{kind}", item.id, "ChargingSession", "charging", occurred, payload
    )


def telemetry_event(item: Any) -> DomainEvent:
    payload: dict[str, Any] = {
        "session_id": str(item.session_id),
        "sample_id": item.sample_id,
        "source": item.source.value,
        "recorded_at": item.recorded_at.isoformat(),
    }
    for name in ("power_kw", "energy_kwh", "state_of_charge_percent"):
        if getattr(item, name) is not None:
            payload[name] = getattr(item, name)
    return event(
        "telemetry.sample-received",
        item.id,
        "TelemetrySample",
        "telemetry",
        item.recorded_at,
        payload,
    )
