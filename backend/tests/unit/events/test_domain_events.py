from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.events.domain import DeliveryStatus, DomainEvent, EventDelivery
from app.modules.events.infrastructure import ConsumerRegistry


def test_domain_event_is_immutable_and_copies_json_documents() -> None:
    payload = {"owner_id": str(uuid4())}
    item = DomainEvent(
        event_type="reservation.created",
        aggregate_id=uuid4(),
        aggregate_type="Reservation",
        producer_module="charging",
        occurred_at=datetime.now(UTC),
        payload=payload,
    )
    payload["changed"] = True
    assert "changed" not in item.payload
    with pytest.raises((FrozenInstanceError, TypeError)):
        item.payload["changed"] = True  # type: ignore[index]


def test_event_delivery_defaults_to_independent_pending_state() -> None:
    item = EventDelivery(event_id=uuid4(), consumer="analytics")
    assert item.status == DeliveryStatus.PENDING
    assert item.attempts == 0
    assert item.last_error is None


def test_consumer_registration_is_unique_and_filtered_by_contract() -> None:
    registry = ConsumerRegistry()
    registry.register("analytics", lambda event: None, ["reservation.created"])
    assert registry.names_for("reservation.created") == ["analytics"]
    assert registry.names_for("reservation.cancelled") == []
    with pytest.raises(ValueError):
        registry.register("analytics", lambda event: None)
