from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.charging.domain.facility import Facility
from app.modules.charging.domain.station import ChargingStation, Connector


class FacilityRepository(ABC):
    @abstractmethod
    def add(self, facility: Facility) -> Facility: ...

    @abstractmethod
    def get(self, facility_id: UUID) -> Facility | None: ...

    @abstractmethod
    def list(self) -> list[Facility]: ...

    @abstractmethod
    def update(self, facility: Facility) -> Facility: ...

    @abstractmethod
    def exists_by_name(self, name: str, *, exclude_id: UUID | None = None) -> bool: ...


class ChargingStationRepository(ABC):
    @abstractmethod
    def add(self, station: ChargingStation) -> ChargingStation: ...

    @abstractmethod
    def get(self, station_id: UUID) -> ChargingStation | None: ...

    @abstractmethod
    def list_by_facility(self, facility_id: UUID) -> list[ChargingStation]: ...

    @abstractmethod
    def update(self, station: ChargingStation) -> ChargingStation: ...

    @abstractmethod
    def exists_by_serial_number(
        self, serial_number: str, *, exclude_id: UUID | None = None
    ) -> bool: ...

    @abstractmethod
    def add_connector(self, station_id: UUID, connector: Connector) -> Connector: ...

    @abstractmethod
    def get_connector(self, connector_id: UUID) -> Connector | None: ...

    @abstractmethod
    def update_connector(self, connector: Connector) -> Connector: ...
