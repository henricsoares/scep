from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from app.modules.charging.domain.reservation import normalize_utc


class ChargingSessionStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class ChargingSession:
    id: UUID
    reservation_id: UUID
    owner_id: UUID
    vehicle_id: UUID
    connector_id: UUID
    status: ChargingSessionStatus
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def activate(
        cls,
        *,
        reservation_id: UUID,
        owner_id: UUID,
        vehicle_id: UUID,
        connector_id: UUID,
        now: datetime,
    ) -> ChargingSession:
        current = normalize_utc(now)
        return cls(
            id=uuid4(),
            reservation_id=reservation_id,
            owner_id=owner_id,
            vehicle_id=vehicle_id,
            connector_id=connector_id,
            status=ChargingSessionStatus.ACTIVE,
            started_at=current,
            ended_at=None,
            created_at=current,
            updated_at=current,
        )

    def complete(self, *, now: datetime) -> ChargingSession:
        if self.status != ChargingSessionStatus.ACTIVE:
            raise ValueError("only ACTIVE charging sessions may be completed")
        current = normalize_utc(now)
        if current < self.started_at:
            raise ValueError("completion cannot precede activation")
        return replace(
            self,
            status=ChargingSessionStatus.COMPLETED,
            ended_at=current,
            updated_at=current,
        )
