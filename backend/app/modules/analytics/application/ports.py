from datetime import datetime
from typing import Any, Protocol
from uuid import UUID


class AnalyticsReader(Protocol):
    def facilities(self) -> list[Any]: ...

    def stations(self) -> list[Any]: ...

    def connectors(self) -> list[Any]: ...

    def reservations(
        self,
        connector_ids: tuple[UUID, ...],
        start: datetime,
        end: datetime,
        reservation_ids: tuple[UUID, ...] = (),
    ) -> list[Any]: ...

    def sessions(
        self,
        connector_ids: tuple[UUID, ...],
        start: datetime,
        end: datetime,
        reservation_ids: tuple[UUID, ...] = (),
    ) -> list[Any]: ...

    def telemetry(
        self, session_ids: tuple[UUID, ...], start: datetime, end: datetime
    ) -> list[Any]: ...
