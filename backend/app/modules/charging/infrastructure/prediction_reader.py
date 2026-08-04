from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.charging.application.prediction import PredictionInfrastructureScope
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel


class ChargingPredictionReader:
    def __init__(self, session: Session) -> None:
        self.session = session

    def resolve_scope(
        self,
        *,
        facility_id: UUID,
        station_id: UUID | None,
        connector_id: UUID | None,
    ) -> PredictionInfrastructureScope:
        facility = self.session.get(FacilityModel, facility_id)
        if facility is None:
            raise LookupError("facility not found")
        station = self.session.get(ChargingStationModel, station_id) if station_id else None
        connector = self.session.get(ConnectorModel, connector_id) if connector_id else None
        if station_id is not None and station is None:
            raise LookupError("charging station not found")
        if connector_id is not None and connector is None:
            raise LookupError("connector not found")
        if station is not None and station.facility_id != facility.id:
            raise ValueError("charging station does not belong to facility")
        if connector is not None and (
            station is None or connector.charging_station_id != station.id
        ):
            raise ValueError("connector does not belong to charging station")
        return PredictionInfrastructureScope(
            facility_id=facility.id,
            facility_timezone=facility.timezone,
            facility_status=facility.status,
            operating_hours=facility.operating_hours,
            station_id=station.id if station else None,
            station_status=station.status if station else None,
            connector_id=connector.id if connector else None,
            connector_status=connector.status if connector else None,
        )

    def connector_candidates(
        self,
        *,
        facility_id: UUID | None = None,
        station_id: UUID | None = None,
    ) -> list[PredictionInfrastructureScope]:
        stmt = (
            select(FacilityModel, ChargingStationModel, ConnectorModel)
            .join(ChargingStationModel, ChargingStationModel.facility_id == FacilityModel.id)
            .join(ConnectorModel, ConnectorModel.charging_station_id == ChargingStationModel.id)
        )
        if facility_id is not None:
            stmt = stmt.where(FacilityModel.id == facility_id)
        if station_id is not None:
            stmt = stmt.where(ChargingStationModel.id == station_id)
        stmt = stmt.order_by(FacilityModel.id, ChargingStationModel.id, ConnectorModel.id)
        return [
            PredictionInfrastructureScope(
                facility_id=facility.id,
                facility_timezone=facility.timezone,
                facility_status=facility.status,
                operating_hours=facility.operating_hours,
                station_id=station.id,
                station_status=station.status,
                connector_id=connector.id,
                connector_status=connector.status,
            )
            for facility, station, connector in self.session.execute(stmt)
        ]
