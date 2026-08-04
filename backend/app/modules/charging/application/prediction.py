from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any, Protocol
from uuid import UUID

from app.modules.charging.domain.facility import FacilityStatus
from app.modules.charging.domain.station import ChargingStationStatus, ConnectorStatus


@dataclass(frozen=True, slots=True)
class PredictionInfrastructureScope:
    facility_id: UUID
    facility_timezone: str
    facility_status: str
    operating_hours: dict[str, Any] | None
    station_id: UUID | None = None
    station_status: str | None = None
    connector_id: UUID | None = None
    connector_status: str | None = None

    @property
    def publication_eligible(self) -> bool:
        if self.facility_status != FacilityStatus.ACTIVE.value:
            return False
        if (
            self.station_id is not None
            and self.station_status != ChargingStationStatus.ACTIVE.value
        ):
            return False
        return not (
            self.connector_id is not None
            and self.connector_status == ConnectorStatus.OUT_OF_SERVICE.value
        )

    def driver_eligible(self, weekday_index: int, hour_of_day: int) -> bool:
        return bool(
            self.facility_status == FacilityStatus.ACTIVE.value
            and (
                self.station_id is None or self.station_status == ChargingStationStatus.ACTIVE.value
            )
            and (
                self.connector_id is None
                or self.connector_status == ConnectorStatus.AVAILABLE.value
            )
            and facility_open_for_hour(self.operating_hours, weekday_index, hour_of_day)
        )


class PredictionInfrastructureReadPort(Protocol):
    def resolve_scope(
        self,
        *,
        facility_id: UUID,
        station_id: UUID | None,
        connector_id: UUID | None,
    ) -> PredictionInfrastructureScope: ...

    def connector_candidates(
        self,
        *,
        facility_id: UUID | None = None,
        station_id: UUID | None = None,
    ) -> list[PredictionInfrastructureScope]: ...


_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_WEEK_MINUTES = 7 * 24 * 60


def _minute(value: object) -> int:
    parsed = time.fromisoformat(str(value))
    return parsed.hour * 60 + parsed.minute


def facility_open_for_hour(
    operating_hours: dict[str, Any] | None, weekday_index: int, hour_of_day: int
) -> bool:
    """Return whether a recurring local hour has any configured Operational Capacity."""
    if not operating_hours:
        return True
    bucket_start = weekday_index * 24 * 60 + hour_of_day * 60
    bucket_end = bucket_start + 60
    for day_index, day in enumerate(_WEEKDAYS):
        configured = operating_hours.get(day)
        rules = configured if isinstance(configured, list) else [configured]
        for rule in rules:
            if not isinstance(rule, dict) or not rule.get("opens") or not rule.get("closes"):
                continue
            try:
                opens = day_index * 24 * 60 + _minute(rule["opens"])
                closes = day_index * 24 * 60 + _minute(rule["closes"])
            except ValueError:
                continue
            if closes <= opens:
                closes += 24 * 60
            for shift in (-_WEEK_MINUTES, 0, _WEEK_MINUTES):
                if max(bucket_start, opens + shift) < min(bucket_end, closes + shift):
                    return True
    return False
