from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.modules.charging.domain.charging_session import (
    ChargingSession,
    ChargingSessionStatus,
)


def test_charging_session_lifecycle_and_immutable_identity() -> None:
    now = datetime(2026, 7, 14, 12, tzinfo=UTC)
    item = ChargingSession.activate(
        reservation_id=uuid4(),
        owner_id=uuid4(),
        vehicle_id=uuid4(),
        connector_id=uuid4(),
        now=now,
    )

    assert item.status == ChargingSessionStatus.ACTIVE
    assert item.started_at == now
    assert item.ended_at is None
    with pytest.raises(FrozenInstanceError):
        item.owner_id = uuid4()  # type: ignore[misc]

    completed = item.complete(now=now + timedelta(hours=1))
    assert completed.status == ChargingSessionStatus.COMPLETED
    assert completed.ended_at == now + timedelta(hours=1)
    assert completed.reservation_id == item.reservation_id
    assert completed.started_at == item.started_at
    with pytest.raises(ValueError, match="only ACTIVE"):
        completed.complete(now=now + timedelta(hours=2))


def test_charging_session_rejects_completion_before_activation() -> None:
    now = datetime(2026, 7, 14, 12, tzinfo=UTC)
    item = ChargingSession.activate(
        reservation_id=uuid4(),
        owner_id=uuid4(),
        vehicle_id=uuid4(),
        connector_id=uuid4(),
        now=now,
    )
    with pytest.raises(ValueError, match="precede"):
        item.complete(now=now - timedelta(seconds=1))
