from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class TelemetryExportRow:
    telemetry_sample_id: UUID
    sample_id: str
    source: str
    session_id: UUID
    reservation_id: UUID
    owner_id: UUID
    vehicle_id: UUID
    facility_id: UUID
    station_id: UUID
    connector_id: UUID
    session_status: str
    session_started_at: datetime
    session_ended_at: datetime | None
    recorded_at: datetime
    received_at: datetime
    power_kw: float | None
    energy_kwh: float | None
    state_of_charge_percent: float | None
    created_at: datetime


class TelemetryDatasetReadPort(Protocol):
    def telemetry(
        self,
        *,
        start: datetime,
        end: datetime,
        cutoff: datetime,
        facility_id: UUID | None,
        station_id: UUID | None,
        connector_id: UUID | None,
        session_id: UUID | None,
    ) -> list[TelemetryExportRow]: ...
