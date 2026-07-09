from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class FacilityType(StrEnum):
    RESIDENTIAL = "Residential"
    COMMERCIAL = "Commercial"
    UNIVERSITY = "University"
    INDUSTRIAL = "Industrial"
    PUBLIC_PARKING = "Public Parking"
    SHOPPING_CENTER = "Shopping Center"
    CORPORATE_CAMPUS = "Corporate Campus"


class FacilityStatus(StrEnum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    UNDER_MAINTENANCE = "Under Maintenance"


@dataclass(frozen=True)
class Facility:
    id: UUID
    name: str
    facility_type: FacilityType
    timezone: str
    country: str
    city: str
    address: str
    latitude: float | None
    longitude: float | None
    operating_hours: dict[str, Any] | None
    status: FacilityStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        name: str,
        facility_type: FacilityType,
        timezone: str,
        country: str,
        city: str,
        address: str,
        latitude: float | None = None,
        longitude: float | None = None,
        operating_hours: dict[str, Any] | None = None,
        status: FacilityStatus = FacilityStatus.ACTIVE,
    ) -> Facility:
        now = datetime.now(UTC)
        facility = cls(
            id=uuid4(),
            name=name,
            facility_type=facility_type,
            timezone=timezone,
            country=country,
            city=city,
            address=address,
            latitude=latitude,
            longitude=longitude,
            operating_hours=operating_hours,
            status=status,
            created_at=now,
            updated_at=now,
        )
        facility.validate()
        return facility

    def update(
        self,
        *,
        name: str,
        facility_type: FacilityType,
        timezone: str,
        country: str,
        city: str,
        address: str,
        latitude: float | None,
        longitude: float | None,
        operating_hours: dict[str, Any] | None,
        status: FacilityStatus,
    ) -> Facility:
        updated = replace(
            self,
            name=name,
            facility_type=facility_type,
            timezone=timezone,
            country=country,
            city=city,
            address=address,
            latitude=latitude,
            longitude=longitude,
            operating_hours=operating_hours,
            status=status,
            updated_at=datetime.now(UTC),
        )
        updated.validate()
        return updated

    def validate(self) -> None:
        for field_name in ("name", "timezone", "country", "city", "address"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} is required")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("timezone must be a valid IANA time zone") from exc
        if self.latitude is not None and not -90 <= self.latitude <= 90:
            raise ValueError("latitude must be between -90 and 90")
        if self.longitude is not None and not -180 <= self.longitude <= 180:
            raise ValueError("longitude must be between -180 and 180")
