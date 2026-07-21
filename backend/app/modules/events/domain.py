from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from uuid import UUID, uuid4


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    FAILED = "FAILED"


class EventType(StrEnum):
    RESERVATION_CREATED = "reservation.created"
    RESERVATION_RESCHEDULED = "reservation.rescheduled"
    RESERVATION_CANCELLED = "reservation.cancelled"
    RESERVATION_MARKED_NO_SHOW = "reservation.marked-no-show"
    CHARGING_SESSION_STARTED = "charging-session.started"
    CHARGING_SESSION_COMPLETED = "charging-session.completed"
    TELEMETRY_SAMPLE_RECEIVED = "telemetry.sample-received"
    DATASET_EXPORT_COMPLETED = "dataset-export.completed"


@dataclass(frozen=True, slots=True)
class DomainEvent:
    event_type: str
    aggregate_id: UUID
    aggregate_type: str
    producer_module: str
    occurred_at: datetime
    payload: Mapping[str, Any]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    correlation_id: UUID | None = None
    causation_id: UUID | None = None
    event_version: int = 1
    id: UUID = field(default_factory=uuid4)
    recorded_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.event_version < 1 or not self.event_type or not self.payload:
            raise ValueError("event type, positive version and payload are required")
        for name in ("occurred_at", "recorded_at", "created_at"):
            value = getattr(self, name)
            if value.tzinfo is None:
                raise ValueError(f"{name} must be timezone-aware")
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(slots=True)
class EventDelivery:
    event_id: UUID
    consumer: str
    status: DeliveryStatus = DeliveryStatus.PENDING
    attempts: int = 0
    id: UUID = field(default_factory=uuid4)
    last_attempt_at: datetime | None = None
    delivered_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not self.consumer or self.attempts < 0:
            raise ValueError("consumer is required and attempts cannot be negative")
