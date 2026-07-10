from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.charging.domain.repositories import ChargingStationRepository
from app.modules.charging.domain.station import (
    ChargingStation,
    ChargingStationStatus,
    Connector,
    ConnectorStatus,
    ConnectorType,
)
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel


class SqlAlchemyChargingStationRepository(ChargingStationRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, station: ChargingStation) -> ChargingStation:
        model = self._to_model(station)
        self.session.add(model)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        return self.get(station.id) or station

    def get(self, station_id: UUID) -> ChargingStation | None:
        stmt = (
            select(ChargingStationModel)
            .options(selectinload(ChargingStationModel.connectors))
            .where(ChargingStationModel.id == station_id)
        )
        model = self.session.scalar(stmt)
        return None if model is None else self._to_domain(model)

    def list_by_facility(self, facility_id: UUID) -> list[ChargingStation]:
        stmt = (
            select(ChargingStationModel)
            .options(selectinload(ChargingStationModel.connectors))
            .where(ChargingStationModel.facility_id == facility_id)
            .order_by(ChargingStationModel.created_at)
        )
        return [self._to_domain(model) for model in self.session.scalars(stmt).all()]

    def update(self, station: ChargingStation) -> ChargingStation:
        model = self.session.get(ChargingStationModel, station.id)
        if model is None:
            raise ValueError("station not found")
        model.name = station.name
        model.description = station.description
        model.status = station.status.value
        model.updated_at = station.updated_at
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        return self.get(station.id) or station

    def exists_by_serial_number(
        self, serial_number: str, *, exclude_id: UUID | None = None
    ) -> bool:
        stmt = select(ChargingStationModel.id).where(
            ChargingStationModel.serial_number == serial_number
        )
        if exclude_id is not None:
            stmt = stmt.where(ChargingStationModel.id != exclude_id)
        return self.session.scalar(stmt) is not None

    def add_connector(self, station_id: UUID, connector: Connector) -> Connector:
        model = self._connector_to_model(connector)
        self.session.add(model)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        self.session.refresh(model)
        return self._connector_to_domain(model)

    def get_connector(self, connector_id: UUID) -> Connector | None:
        model = self.session.get(ConnectorModel, connector_id)
        return None if model is None else self._connector_to_domain(model)

    def update_connector(self, connector: Connector) -> Connector:
        model = self.session.get(ConnectorModel, connector.id)
        if model is None:
            raise ValueError("connector not found")
        model.status = connector.status.value
        model.updated_at = connector.updated_at
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        self.session.refresh(model)
        return self._connector_to_domain(model)

    def _to_model(self, station: ChargingStation) -> ChargingStationModel:
        return ChargingStationModel(
            id=station.id,
            facility_id=station.facility_id,
            name=station.name,
            description=station.description,
            serial_number=station.serial_number,
            manufacturer=station.manufacturer,
            model=station.model,
            maximum_power_kw=station.maximum_power_kw,
            status=station.status.value,
            created_at=station.created_at,
            updated_at=station.updated_at,
            connectors=[self._connector_to_model(c) for c in station.connectors],
        )

    def _to_domain(self, model: ChargingStationModel) -> ChargingStation:
        return ChargingStation(
            id=model.id,
            facility_id=model.facility_id,
            name=model.name,
            description=model.description,
            serial_number=model.serial_number,
            manufacturer=model.manufacturer,
            model=model.model,
            maximum_power_kw=model.maximum_power_kw,
            status=ChargingStationStatus(model.status),
            connectors=tuple(
                self._connector_to_domain(c)
                for c in sorted(model.connectors, key=lambda c: c.created_at)
            ),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _connector_to_model(self, connector: Connector) -> ConnectorModel:
        return ConnectorModel(
            id=connector.id,
            charging_station_id=connector.charging_station_id,
            connector_type=connector.connector_type.value,
            maximum_power_kw=connector.maximum_power_kw,
            status=connector.status.value,
            created_at=connector.created_at,
            updated_at=connector.updated_at,
        )

    def _connector_to_domain(self, model: ConnectorModel) -> Connector:
        return Connector(
            id=model.id,
            charging_station_id=model.charging_station_id,
            connector_type=ConnectorType(model.connector_type),
            maximum_power_kw=model.maximum_power_kw,
            status=ConnectorStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
