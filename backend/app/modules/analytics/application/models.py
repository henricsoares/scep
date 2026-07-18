from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class Granularity(StrEnum):
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


@dataclass(frozen=True)
class AnalyticsQuery:
    from_: datetime
    to: datetime
    facility_id: UUID | None = None
    station_id: UUID | None = None
    connector_id: UUID | None = None
    timezone: str | None = None
    granularity: Granularity | None = None


@dataclass(frozen=True)
class Scope:
    facility_ids: tuple[UUID, ...]
    connector_ids: tuple[UUID, ...]
    timezone: str


Metrics = dict[str, int | float | None]
Response = dict[str, Any]
