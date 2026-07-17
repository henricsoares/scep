from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.events.domain import DeliveryStatus, DomainEvent
from app.modules.events.infrastructure import ConsumerRegistry, EventDeliveryModel, registry
from app.modules.events.metrics import (
    deliveries_total,
    delivery_failures_total,
    delivery_retries_total,
    pending_deliveries,
)

logger = logging.getLogger(__name__)


class InternalEventDispatcher:
    def __init__(
        self, sessions: sessionmaker[Session], consumers: ConsumerRegistry = registry
    ) -> None:
        self.sessions, self.consumers = sessions, consumers

    def recover(self, *, limit: int = 100) -> int:
        processed = 0
        attempted: set[object] = set()
        while processed < limit:
            delivery_id = self.dispatch_one(exclude=attempted)
            if delivery_id is None:
                break
            attempted.add(delivery_id)
            processed += 1
        with self.sessions() as session:
            pending_deliveries.set(
                session.scalar(
                    select(func.count())
                    .select_from(EventDeliveryModel)
                    .where(
                        EventDeliveryModel.status.in_(
                            [DeliveryStatus.PENDING.value, DeliveryStatus.FAILED.value]
                        )
                    )
                )
                or 0
            )
        logger.info("domain event recovery completed", extra={"deliveries_processed": processed})
        return processed

    def dispatch_one(self, *, exclude: set[object] | None = None) -> object | None:
        with self.sessions() as session:
            stmt = select(EventDeliveryModel).where(
                EventDeliveryModel.status.in_(
                    [DeliveryStatus.PENDING.value, DeliveryStatus.FAILED.value]
                )
            )
            if exclude:
                stmt = stmt.where(EventDeliveryModel.id.not_in(exclude))
            delivery = session.scalar(
                stmt.order_by(EventDeliveryModel.updated_at, EventDeliveryModel.id)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if delivery is None:
                return None
            now = datetime.now(UTC)
            retry = delivery.attempts > 0
            delivery.attempts += 1
            delivery.last_attempt_at = now
            delivery.updated_at = now
            event = delivery.event
            domain = DomainEvent(
                event_type=event.event_type,
                aggregate_id=event.aggregate_id,
                aggregate_type=event.aggregate_type,
                producer_module=event.producer_module,
                occurred_at=event.occurred_at,
                payload=event.payload,
                metadata=event.event_metadata,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                event_version=event.event_version,
                id=event.id,
                recorded_at=event.recorded_at,
                created_at=event.created_at,
            )
            if retry:
                delivery_retries_total.labels(delivery.consumer).inc()
                logger.info(
                    "domain event delivery retry",
                    extra={
                        "event_id": str(event.id),
                        "delivery_id": str(delivery.id),
                        "consumer": delivery.consumer,
                    },
                )
            try:
                logger.info(
                    "domain event consumer execution",
                    extra={
                        "event_id": str(event.id),
                        "delivery_id": str(delivery.id),
                        "consumer": delivery.consumer,
                        "event_type": event.event_type,
                    },
                )
                self.consumers.get(delivery.consumer)(domain)
            except Exception as exc:
                delivery.status = DeliveryStatus.FAILED.value
                delivery.last_error = str(exc)[:2000]
                delivery_failures_total.labels(delivery.consumer).inc()
                logger.exception(
                    "domain event delivery failed",
                    extra={
                        "event_id": str(event.id),
                        "delivery_id": str(delivery.id),
                        "consumer": delivery.consumer,
                    },
                )
            else:
                delivery.status = DeliveryStatus.DISPATCHED.value
                delivery.delivered_at = now
                delivery.last_error = None
                deliveries_total.labels(delivery.consumer).inc()
                logger.info(
                    "domain event delivered",
                    extra={
                        "event_id": str(event.id),
                        "delivery_id": str(delivery.id),
                        "consumer": delivery.consumer,
                    },
                )
            session.commit()
            return delivery.id
