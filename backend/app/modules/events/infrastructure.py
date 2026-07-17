from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy import event as sa_event
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.infrastructure.database import Base
from app.modules.events.domain import DeliveryStatus, DomainEvent
from app.modules.events.metrics import events_persisted_total, registered_consumers

logger = logging.getLogger(__name__)


class DomainEventModel(Base):
    __tablename__ = "domain_events"
    __table_args__ = (
        CheckConstraint("event_version > 0", name="ck_domain_events_version"),
        Index("ix_domain_events_occurred_id", "occurred_at", "id"),
        Index("ix_domain_events_type", "event_type"),
        Index("ix_domain_events_aggregate", "aggregate_type", "aggregate_id"),
        Index("ix_domain_events_producer", "producer_module"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(128), nullable=False)
    producer_module: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    correlation_id: Mapped[UUID | None]
    causation_id: Mapped[UUID | None]
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deliveries: Mapped[list[EventDeliveryModel]] = relationship(
        back_populates="event", lazy="selectin"
    )


class EventDeliveryModel(Base):
    __tablename__ = "event_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING','DISPATCHED','FAILED')", name="ck_event_delivery_status"
        ),
        CheckConstraint("attempts >= 0", name="ck_event_delivery_attempts"),
        Index("uq_event_delivery_event_consumer", "event_id", "consumer", unique=True),
        Index("ix_event_delivery_eligible", "status", "updated_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_id: Mapped[UUID] = mapped_column(
        ForeignKey("domain_events.id", ondelete="RESTRICT"), nullable=False
    )
    consumer: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event: Mapped[DomainEventModel] = relationship(back_populates="deliveries")


Consumer = Callable[[DomainEvent], None]


class ConsumerRegistry:
    def __init__(self) -> None:
        self._consumers: dict[str, tuple[Consumer, frozenset[str] | None]] = {}

    def register(
        self, name: str, consumer: Consumer, event_types: Iterable[str] | None = None
    ) -> None:
        if not name or name in self._consumers:
            raise ValueError("consumer name must be unique")
        self._consumers[name] = (consumer, None if event_types is None else frozenset(event_types))
        registered_consumers.set(len(self._consumers))

    def names_for(self, event_type: str) -> list[str]:
        return [
            name
            for name, (_, types) in self._consumers.items()
            if types is None or event_type in types
        ]

    def get(self, name: str) -> Consumer:
        return self._consumers[name][0]


registry = ConsumerRegistry()
_post_commit_dispatch: Callable[[], object] | None = None


def configure_post_commit_dispatch(callback: Callable[[], object]) -> None:
    global _post_commit_dispatch
    _post_commit_dispatch = callback


class EventPublisher:
    def __init__(self, session: Session, consumers: ConsumerRegistry = registry) -> None:
        self.session, self.consumers = session, consumers

    def publish(self, item: DomainEvent) -> None:
        model = DomainEventModel(
            id=item.id,
            event_type=item.event_type,
            event_version=item.event_version,
            aggregate_id=item.aggregate_id,
            aggregate_type=item.aggregate_type,
            producer_module=item.producer_module,
            occurred_at=item.occurred_at,
            recorded_at=item.recorded_at,
            correlation_id=item.correlation_id,
            causation_id=item.causation_id,
            payload=dict(item.payload),
            event_metadata=dict(item.metadata),
            created_at=item.created_at,
        )
        self.session.add(model)
        now = datetime.now(UTC)
        for consumer in self.consumers.names_for(item.event_type):
            self.session.add(
                EventDeliveryModel(
                    id=uuid4(),
                    event_id=item.id,
                    consumer=consumer,
                    status=DeliveryStatus.PENDING.value,
                    attempts=0,
                    created_at=now,
                    updated_at=now,
                )
            )
        if isinstance(self.session.info, dict):
            published = self.session.info.get("domain_events_published", [])
            if not isinstance(published, list):
                published = []
            self.session.info["domain_events_published"] = published + [item.event_type]
        logger.info(
            "domain event persisted",
            extra={
                "event_id": str(item.id),
                "event_type": item.event_type,
                "aggregate_id": str(item.aggregate_id),
            },
        )


@sa_event.listens_for(Session, "after_commit")
def _after_commit(session: Session) -> None:
    published = session.info.pop("domain_events_published", [])
    for event_type in published:
        events_persisted_total.labels(event_type).inc()
    if published and _post_commit_dispatch is not None:
        _post_commit_dispatch()
