from typing import Any

import pytest
from app.modules.charging.domain.facility import Facility, FacilityStatus, FacilityType


def test_create_facility() -> None:
    facility = Facility.create(
        name="North Campus",
        facility_type=FacilityType.UNIVERSITY,
        timezone="America/New_York",
        country="United States",
        city="New York",
        address="123 Main St",
        latitude=40.0,
        longitude=-73.0,
        operating_hours={"monday": {"opens": "08:00", "closes": "22:00"}},
        status=FacilityStatus.ACTIVE,
    )
    assert facility.name == "North Campus"
    assert facility.id is not None


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("name", "", "name is required"),
        ("timezone", "Invalid/Zone", "timezone must be a valid IANA time zone"),
        ("latitude", 91.0, "latitude must be between -90 and 90"),
        ("longitude", 181.0, "longitude must be between -180 and 180"),
    ],
)
def test_facility_validation(field: str, value: object, message: str) -> None:
    kwargs: dict[str, Any] = {
        "name": "North Campus",
        "facility_type": FacilityType.UNIVERSITY,
        "timezone": "America/New_York",
        "country": "United States",
        "city": "New York",
        "address": "123 Main St",
        "latitude": 40.0,
        "longitude": -73.0,
        "operating_hours": None,
        "status": FacilityStatus.ACTIVE,
    }
    kwargs[field] = value
    with pytest.raises(ValueError, match=message):
        Facility.create(**kwargs)


def test_update_preserves_identifier() -> None:
    facility = Facility.create(
        name="North Campus",
        facility_type=FacilityType.UNIVERSITY,
        timezone="America/New_York",
        country="United States",
        city="New York",
        address="123 Main St",
        status=FacilityStatus.ACTIVE,
    )
    updated = facility.update(
        name="South Campus",
        facility_type=FacilityType.COMMERCIAL,
        timezone="America/New_York",
        country="United States",
        city="New York",
        address="456 Main St",
        latitude=None,
        longitude=None,
        operating_hours=None,
        status=FacilityStatus.INACTIVE,
    )
    assert updated.id == facility.id
    assert updated.created_at == facility.created_at
    assert updated.updated_at >= facility.updated_at
