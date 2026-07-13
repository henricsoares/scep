from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class VehicleStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


def _display_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("display_name is required")
    if len(normalized) > 255:
        raise ValueError("display_name must contain at most 255 characters")
    return normalized


@dataclass(frozen=True)
class Vehicle:
    id: UUID
    owner_id: UUID
    display_name: str
    status: VehicleStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, *, owner_id: UUID, display_name: str, now: datetime) -> Vehicle:
        name = _display_name(display_name)
        return cls(uuid4(), owner_id, name, VehicleStatus.ACTIVE, now, now)

    def rename(self, display_name: str, *, now: datetime) -> Vehicle:
        return replace(self, display_name=_display_name(display_name), updated_at=now)

    def activate(self, *, now: datetime) -> Vehicle:
        return replace(self, status=VehicleStatus.ACTIVE, updated_at=now)

    def deactivate(self, *, now: datetime) -> Vehicle:
        return replace(self, status=VehicleStatus.INACTIVE, updated_at=now)
