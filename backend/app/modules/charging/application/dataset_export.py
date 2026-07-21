from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ChargingSessionExportRow:
    session_id: UUID
    reservation_id: UUID
    owner_id: UUID
    vehicle_id: UUID
    facility_id: UUID
    station_id: UUID
    connector_id: UUID
    status: str
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ChargingDatasetReadPort(Protocol):
    def validate_scope(
        self,
        *,
        facility_id: UUID | None,
        station_id: UUID | None,
        connector_id: UUID | None,
        session_id: UUID | None = None,
    ) -> None: ...

    def charging_sessions(
        self,
        *,
        start: datetime,
        end: datetime,
        facility_id: UUID | None,
        station_id: UUID | None,
        connector_id: UUID | None,
    ) -> list[ChargingSessionExportRow]: ...
