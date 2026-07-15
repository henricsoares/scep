from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from app.modules.charging.domain.reservation import normalize_utc


class TelemetrySource(StrEnum):
    SIMULATOR = "SIMULATOR"
    API_CLIENT = "API_CLIENT"


@dataclass(frozen=True)
class TelemetrySample:
    id: UUID
    session_id: UUID
    sample_id: str
    source: TelemetrySource
    recorded_at: datetime
    received_at: datetime
    power_kw: float | None
    energy_kwh: float | None
    state_of_charge_percent: float | None
    created_at: datetime

    @classmethod
    def create(
        cls,
        *,
        session_id: UUID,
        sample_id: str,
        source: TelemetrySource,
        recorded_at: datetime,
        received_at: datetime,
        power_kw: float | None = None,
        energy_kwh: float | None = None,
        state_of_charge_percent: float | None = None,
    ) -> TelemetrySample:
        sample_id = sample_id.strip()
        if not sample_id:
            raise ValueError("sample_id is required")
        measurements = (power_kw, energy_kwh, state_of_charge_percent)
        if all(value is None for value in measurements):
            raise ValueError("at least one measurement is required")
        for value in measurements:
            if value is not None and not math.isfinite(value):
                raise ValueError("measurements must be finite")
        if power_kw is not None and power_kw < 0:
            raise ValueError("power_kw must be non-negative")
        if energy_kwh is not None and energy_kwh < 0:
            raise ValueError("energy_kwh must be non-negative")
        if state_of_charge_percent is not None and not 0 <= state_of_charge_percent <= 100:
            raise ValueError("state_of_charge_percent must be between 0 and 100")
        received = normalize_utc(received_at)
        return cls(
            id=uuid4(),
            session_id=session_id,
            sample_id=sample_id,
            source=source,
            recorded_at=normalize_utc(recorded_at),
            received_at=received,
            power_kw=power_kw,
            energy_kwh=energy_kwh,
            state_of_charge_percent=state_of_charge_percent,
            created_at=received,
        )

    @property
    def idempotency_key(self) -> tuple[UUID, TelemetrySource, str]:
        return self.session_id, self.source, self.sample_id

    def same_producer_payload(self, other: TelemetrySample) -> bool:
        return (
            self.idempotency_key == other.idempotency_key
            and self.recorded_at == other.recorded_at
            and self.power_kw == other.power_kw
            and self.energy_kwh == other.energy_kwh
            and self.state_of_charge_percent == other.state_of_charge_percent
        )
