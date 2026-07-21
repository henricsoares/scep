from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.charging.application.dataset_export import ChargingSessionExportRow
from app.modules.charging.infrastructure.charging_session_model import ChargingSessionModel
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel


class ChargingDatasetReader:
    def __init__(self, session: Session) -> None:
        self.session = session

    def validate_scope(
        self,
        *,
        facility_id: UUID | None,
        station_id: UUID | None,
        connector_id: UUID | None,
        session_id: UUID | None = None,
    ) -> None:
        facility = self.session.get(FacilityModel, facility_id) if facility_id else None
        station = self.session.get(ChargingStationModel, station_id) if station_id else None
        connector = self.session.get(ConnectorModel, connector_id) if connector_id else None
        session = self.session.get(ChargingSessionModel, session_id) if session_id else None
        if facility_id and facility is None:
            raise LookupError("facility not found")
        if station_id and station is None:
            raise LookupError("charging station not found")
        if connector_id and connector is None:
            raise LookupError("connector not found")
        if session_id and session is None:
            raise LookupError("charging session not found")
        if station and facility_id and station.facility_id != facility_id:
            raise ValueError("charging station does not belong to facility")
        if connector and station_id and connector.charging_station_id != station_id:
            raise ValueError("connector does not belong to charging station")
        if connector and facility_id:
            owner_station = self.session.get(ChargingStationModel, connector.charging_station_id)
            if owner_station is None or owner_station.facility_id != facility_id:
                raise ValueError("connector does not belong to facility")
        if session and connector_id and session.connector_id != connector_id:
            raise ValueError("charging session does not belong to connector")
        if session and station_id:
            session_connector = self.session.get(ConnectorModel, session.connector_id)
            if session_connector is None or session_connector.charging_station_id != station_id:
                raise ValueError("charging session does not belong to charging station")
        if session and facility_id:
            session_connector = self.session.get(ConnectorModel, session.connector_id)
            session_station = (
                self.session.get(ChargingStationModel, session_connector.charging_station_id)
                if session_connector
                else None
            )
            if session_station is None or session_station.facility_id != facility_id:
                raise ValueError("charging session does not belong to facility")

    def charging_sessions(
        self,
        *,
        start: datetime,
        end: datetime,
        facility_id: UUID | None,
        station_id: UUID | None,
        connector_id: UUID | None,
    ) -> list[ChargingSessionExportRow]:
        stmt = (
            select(ChargingSessionModel, ConnectorModel, ChargingStationModel)
            .join(ConnectorModel, ChargingSessionModel.connector_id == ConnectorModel.id)
            .join(
                ChargingStationModel,
                ConnectorModel.charging_station_id == ChargingStationModel.id,
            )
            .where(
                ChargingSessionModel.started_at >= start,
                ChargingSessionModel.started_at < end,
            )
        )
        if facility_id:
            stmt = stmt.where(ChargingStationModel.facility_id == facility_id)
        if station_id:
            stmt = stmt.where(ChargingStationModel.id == station_id)
        if connector_id:
            stmt = stmt.where(ConnectorModel.id == connector_id)
        stmt = stmt.order_by(ChargingSessionModel.started_at, ChargingSessionModel.id)
        return [
            ChargingSessionExportRow(
                session_id=item.id,
                reservation_id=item.reservation_id,
                owner_id=item.owner_id,
                vehicle_id=item.vehicle_id,
                facility_id=station.facility_id,
                station_id=station.id,
                connector_id=connector.id,
                status=item.status,
                started_at=item.started_at,
                ended_at=item.ended_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item, connector, station in self.session.execute(stmt)
        ]
