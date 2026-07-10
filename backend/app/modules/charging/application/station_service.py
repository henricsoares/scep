from uuid import UUID
from typing import Any

from app.modules.charging.domain.facility import FacilityStatus
from app.modules.charging.domain.repositories import ChargingStationRepository, FacilityRepository
from app.modules.charging.domain.station import (
    ChargingStation,
    ChargingStationStatus,
    Connector,
    ConnectorStatus,
    ConnectorType,
)


class ChargingStationNotFoundError(Exception):
    pass


class ConnectorNotFoundError(Exception):
    pass


class FacilityUnavailableError(Exception):
    pass


class ChargingStationSerialNumberAlreadyExistsError(Exception):
    pass


class ChargingStationService:
    def __init__(
        self, station_repository: ChargingStationRepository, facility_repository: FacilityRepository
    ) -> None:
        self.station_repository = station_repository
        self.facility_repository = facility_repository

    def create_station(
        self,
        *,
        facility_id: UUID,
        name: str,
        description: str | None,
        serial_number: str,
        manufacturer: str | None,
        model: str | None,
        maximum_power_kw: float,
        status: ChargingStationStatus,
        connectors: list[tuple[ConnectorType, float, ConnectorStatus]],
    ) -> ChargingStation:
        facility = self.facility_repository.get(facility_id)
        if facility is None:
            raise ChargingStationNotFoundError("facility not found")
        if facility.status != FacilityStatus.ACTIVE:
            raise FacilityUnavailableError("facility must be Active")
        if self.station_repository.exists_by_serial_number(serial_number):
            raise ChargingStationSerialNumberAlreadyExistsError(serial_number)
        station = ChargingStation.create(
            facility_id=facility_id,
            name=name,
            description=description,
            serial_number=serial_number,
            manufacturer=manufacturer,
            model=model,
            maximum_power_kw=maximum_power_kw,
            status=status,
            connectors=connectors,
        )
        return self.station_repository.add(station)

    def list_by_facility(self, facility_id: UUID) -> list[ChargingStation]:
        if self.facility_repository.get(facility_id) is None:
            raise ChargingStationNotFoundError("facility not found")
        return self.station_repository.list_by_facility(facility_id)

    def get_station(self, station_id: UUID) -> ChargingStation:
        station = self.station_repository.get(station_id)
        if station is None:
            raise ChargingStationNotFoundError("station not found")
        return station

    def update_station(self, station_id: UUID, **kwargs: Any) -> ChargingStation:
        station = self.get_station(station_id)
        if not kwargs:
            raise ValueError("empty payload")
        allowed = {"name", "description", "status"}
        for k in kwargs:
            if k not in allowed:
                raise ValueError(f"invalid field: {k}")

        name = kwargs.get("name", station.name)
        description = kwargs.get("description", station.description)
        status = kwargs.get("status", station.status)

        return self.station_repository.update(
            station.update(name=name, description=description, status=status)
        )

    def add_connector(
        self,
        station_id: UUID,
        *,
        connector_type: ConnectorType,
        maximum_power_kw: float,
        status: ConnectorStatus,
    ) -> Connector:
        station = self.get_station(station_id)
        updated = station.add_connector(connector_type, maximum_power_kw, status)
        connector = updated.connectors[-1]
        return self.station_repository.add_connector(station.id, connector)

    def update_connector_status(self, connector_id: UUID, *, status: ConnectorStatus) -> Connector:
        connector = self.station_repository.get_connector(connector_id)
        if connector is None:
            raise ConnectorNotFoundError("connector not found")
        return self.station_repository.update_connector(connector.update_status(status))
