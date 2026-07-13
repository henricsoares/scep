from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.modules.charging.domain.vehicle import Vehicle, VehicleStatus


def test_vehicle_lifecycle_and_immutable_ownership() -> None:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    owner_id = uuid4()
    vehicle = Vehicle.create(owner_id=owner_id, display_name="  Primary EV  ", now=now)
    assert vehicle.display_name == "Primary EV"
    assert vehicle.status == VehicleStatus.ACTIVE

    changed = vehicle.rename("Secondary EV", now=now + timedelta(seconds=1)).deactivate(
        now=now + timedelta(seconds=2)
    )
    assert changed.owner_id == owner_id
    assert changed.status == VehicleStatus.INACTIVE
    assert changed.activate(now=now + timedelta(seconds=3)).status == VehicleStatus.ACTIVE


@pytest.mark.parametrize("name", ["", "   ", "x" * 256])
def test_invalid_display_name(name: str) -> None:
    with pytest.raises(ValueError, match="display_name"):
        Vehicle.create(owner_id=uuid4(), display_name=name, now=datetime(2026, 7, 13, tzinfo=UTC))
