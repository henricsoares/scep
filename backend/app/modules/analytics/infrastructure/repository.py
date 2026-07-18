from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.modules.charging.infrastructure.charging_session_model import ChargingSessionModel
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.charging.infrastructure.reservation_model import ReservationModel
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel
from app.modules.telemetry.infrastructure import TelemetrySampleModel


class AnalyticsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def facilities(self) -> list[FacilityModel]:
        return list(self.session.scalars(select(FacilityModel).order_by(FacilityModel.id)))

    def stations(self) -> list[ChargingStationModel]:
        return list(
            self.session.scalars(select(ChargingStationModel).order_by(ChargingStationModel.id))
        )

    def connectors(self) -> list[ConnectorModel]:
        return list(self.session.scalars(select(ConnectorModel).order_by(ConnectorModel.id)))

    def reservations(
        self, connector_ids: tuple[UUID, ...], start: datetime, end: datetime
    ) -> list[ReservationModel]:
        if not connector_ids:
            return []
        stmt = select(ReservationModel).where(
            ReservationModel.connector_id.in_(connector_ids),
            or_(
                ReservationModel.start_at.between(start, end),
                (ReservationModel.start_at < end) & (ReservationModel.end_at > start),
            ),
        )
        return list(self.session.scalars(stmt))

    def sessions(
        self,
        connector_ids: tuple[UUID, ...],
        start: datetime,
        end: datetime,
        reservation_ids: tuple[UUID, ...] = (),
    ) -> list[ChargingSessionModel]:
        if not connector_ids:
            return []
        overlaps = (ChargingSessionModel.started_at < end) & or_(
            ChargingSessionModel.ended_at.is_(None), ChargingSessionModel.ended_at > start
        )
        selected = overlaps
        if reservation_ids:
            selected = or_(overlaps, ChargingSessionModel.reservation_id.in_(reservation_ids))
        stmt = select(ChargingSessionModel).where(
            ChargingSessionModel.connector_id.in_(connector_ids), selected
        )
        return list(self.session.scalars(stmt))

    def telemetry(
        self, session_ids: tuple[UUID, ...], start: datetime, end: datetime
    ) -> list[TelemetrySampleModel]:
        if not session_ids:
            return []
        stmt = select(TelemetrySampleModel).where(
            TelemetrySampleModel.session_id.in_(session_ids),
            TelemetrySampleModel.recorded_at >= start,
            TelemetrySampleModel.recorded_at < end,
            TelemetrySampleModel.energy_kwh.is_not(None),
        )
        return list(self.session.scalars(stmt))
