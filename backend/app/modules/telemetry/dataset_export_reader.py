from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.charging.infrastructure.charging_session_model import ChargingSessionModel
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel
from app.modules.telemetry.application.dataset_export import TelemetryExportRow
from app.modules.telemetry.infrastructure import TelemetrySampleModel


class TelemetryDatasetReader:
    def __init__(self, session: Session) -> None:
        self.session = session

    def telemetry(
        self,
        *,
        start: datetime,
        end: datetime,
        cutoff: datetime,
        facility_id: UUID | None,
        station_id: UUID | None,
        connector_id: UUID | None,
        session_id: UUID | None,
    ) -> list[TelemetryExportRow]:
        stmt = (
            select(
                TelemetrySampleModel,
                ChargingSessionModel,
                ConnectorModel,
                ChargingStationModel,
            )
            .join(ChargingSessionModel, TelemetrySampleModel.session_id == ChargingSessionModel.id)
            .join(ConnectorModel, ChargingSessionModel.connector_id == ConnectorModel.id)
            .join(
                ChargingStationModel,
                ConnectorModel.charging_station_id == ChargingStationModel.id,
            )
            .where(
                TelemetrySampleModel.recorded_at >= start,
                TelemetrySampleModel.recorded_at < end,
                TelemetrySampleModel.received_at <= cutoff,
            )
        )
        if facility_id:
            stmt = stmt.where(ChargingStationModel.facility_id == facility_id)
        if station_id:
            stmt = stmt.where(ChargingStationModel.id == station_id)
        if connector_id:
            stmt = stmt.where(ConnectorModel.id == connector_id)
        if session_id:
            stmt = stmt.where(ChargingSessionModel.id == session_id)
        stmt = stmt.order_by(
            TelemetrySampleModel.recorded_at,
            TelemetrySampleModel.received_at,
            TelemetrySampleModel.id,
        )
        return [
            TelemetryExportRow(
                telemetry_sample_id=sample.id,
                sample_id=sample.sample_id,
                source=sample.source,
                session_id=session.id,
                reservation_id=session.reservation_id,
                owner_id=session.owner_id,
                vehicle_id=session.vehicle_id,
                facility_id=station.facility_id,
                station_id=station.id,
                connector_id=connector.id,
                session_status=session.status,
                session_started_at=session.started_at,
                session_ended_at=session.ended_at,
                recorded_at=sample.recorded_at,
                received_at=sample.received_at,
                power_kw=sample.power_kw,
                energy_kwh=sample.energy_kwh,
                state_of_charge_percent=sample.state_of_charge_percent,
                created_at=sample.created_at,
            )
            for sample, session, connector, station in self.session.execute(stmt)
        ]
