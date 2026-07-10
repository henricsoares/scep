from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


class ChargingStationStatus(StrEnum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    UNDER_MAINTENANCE = "UnderMaintenance"


class ConnectorType(StrEnum):
    CCS2 = "CCS2"
    CHADEMO = "CHAdeMO"
    NACS = "NACS"
    TYPE2 = "Type2"


class ConnectorStatus(StrEnum):
    AVAILABLE = "Available"
    RESERVED = "Reserved"
    CHARGING = "Charging"
    OUT_OF_SERVICE = "OutOfService"


@dataclass(frozen=True)
class Connector:
    id: UUID
    charging_station_id: UUID
    connector_type: ConnectorType
    maximum_power_kw: float
    status: ConnectorStatus
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        charging_station_id: UUID,
        connector_type: ConnectorType,
        maximum_power_kw: float,
        status: ConnectorStatus = ConnectorStatus.AVAILABLE,
    ) -> Connector:
        now = datetime.now(UTC)
        connector = cls(
            id=uuid4(),
            charging_station_id=charging_station_id,
            connector_type=connector_type,
            maximum_power_kw=maximum_power_kw,
            status=status,
            created_at=now,
            updated_at=now,
        )
        connector.validate()
        return connector

    def validate(self) -> None:
        if self.maximum_power_kw <= 0:
            raise ValueError("connector maximum_power_kw must be greater than zero")

    def update_status(self, status: ConnectorStatus) -> Connector:
        updated = replace(self, status=status, updated_at=datetime.now(UTC))
        updated.validate()
        return updated


@dataclass(frozen=True)
class ChargingStation:
    id: UUID
    facility_id: UUID
    name: str
    description: str | None
    serial_number: str
    manufacturer: str | None
    model: str | None
    maximum_power_kw: float
    status: ChargingStationStatus
    connectors: tuple[Connector, ...]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        *,
        facility_id: UUID,
        name: str,
        description: str | None,
        serial_number: str,
        manufacturer: str | None,
        model: str | None,
        maximum_power_kw: float,
        status: ChargingStationStatus = ChargingStationStatus.ACTIVE,
        connectors: list[tuple[ConnectorType, float, ConnectorStatus]],
    ) -> ChargingStation:
        now = datetime.now(UTC)
        station_id = uuid4()
        station_connectors = tuple(
            Connector.create(
                charging_station_id=station_id,
                connector_type=connector_type,
                maximum_power_kw=connector_power,
                status=connector_status,
            )
            for connector_type, connector_power, connector_status in connectors
        )
        station = cls(
            id=station_id,
            facility_id=facility_id,
            name=name,
            description=description,
            serial_number=serial_number,
            manufacturer=manufacturer,
            model=model,
            maximum_power_kw=maximum_power_kw,
            status=status,
            connectors=station_connectors,
            created_at=now,
            updated_at=now,
        )
        station.validate()
        return station

    def validate(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("name is required")
        if not isinstance(self.serial_number, str) or not self.serial_number.strip():
            raise ValueError("serial_number is required")
        if self.maximum_power_kw <= 0:
            raise ValueError("maximum_power_kw must be greater than zero")
        if not self.connectors:
            raise ValueError("charging station requires at least one connector")
        for connector in self.connectors:
            if connector.charging_station_id != self.id:
                raise ValueError("connector must belong to charging station")
            connector.validate()

    def update(
        self, *, name: str, description: str | None, status: ChargingStationStatus
    ) -> ChargingStation:
        updated = replace(
            self, name=name, description=description, status=status, updated_at=datetime.now(UTC)
        )
        updated.validate()
        return updated

    def add_connector(
        self, connector_type: ConnectorType, maximum_power_kw: float, status: ConnectorStatus
    ) -> ChargingStation:
        connector = Connector.create(
            charging_station_id=self.id,
            connector_type=connector_type,
            maximum_power_kw=maximum_power_kw,
            status=status,
        )
        updated = replace(
            self, connectors=(*self.connectors, connector), updated_at=datetime.now(UTC)
        )
        updated.validate()
        return updated

    def is_operationally_available(self) -> bool:
        return self.status == ChargingStationStatus.ACTIVE
