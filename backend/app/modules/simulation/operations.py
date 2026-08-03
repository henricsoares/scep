from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.charging.infrastructure.charging_session_model import ChargingSessionModel
from app.modules.charging.infrastructure.reservation_model import ReservationModel
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel


def facility_for_connector(session: Session, connector_id: UUID) -> UUID:
    facility_id = session.scalar(
        select(ChargingStationModel.facility_id)
        .join(ConnectorModel, ConnectorModel.charging_station_id == ChargingStationModel.id)
        .where(ConnectorModel.id == connector_id)
    )
    if facility_id is None:
        raise HTTPException(status_code=404, detail="connector not found")
    return facility_id


def reservation_scope(session: Session, reservation_id: UUID, run_id: UUID) -> tuple[UUID, UUID]:
    row = session.execute(
        select(ReservationModel.connector_id, ReservationModel.simulation_run_id).where(
            ReservationModel.id == reservation_id
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="reservation not found")
    connector_id, provenance = row
    if provenance != run_id:
        raise _provenance_error("Reservation")
    return facility_for_connector(session, connector_id), connector_id


def session_scope(session: Session, session_id: UUID, run_id: UUID) -> tuple[UUID, UUID]:
    row = session.execute(
        select(ChargingSessionModel.connector_id, ChargingSessionModel.simulation_run_id).where(
            ChargingSessionModel.id == session_id
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="charging session not found")
    connector_id, provenance = row
    if provenance != run_id:
        raise _provenance_error("Charging Session")
    return facility_for_connector(session, connector_id), connector_id


def _provenance_error(resource: str) -> HTTPException:
    return HTTPException(
        status_code=403,
        detail={
            "code": "SIMULATION_FACILITY_NOT_AUTHORIZED",
            "message": f"{resource} does not belong to this simulation run",
        },
    )
