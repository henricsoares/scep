from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.charging.api.reservations import get_reservation_service
from app.modules.charging.application.charging_session_service import (
    ChargingSessionConflictError,
    ChargingSessionNotFoundError,
    ChargingSessionService,
)
from app.modules.charging.application.reservation_service import ReservationNotFoundError
from app.modules.charging.application.station_service import ConnectorNotFoundError
from app.modules.charging.application.vehicle_service import VehicleNotFoundError
from app.modules.charging.domain.charging_session import ChargingSession, ChargingSessionStatus
from app.modules.charging.domain.reservation import normalize_utc
from app.modules.charging.infrastructure.charging_session_repository import (
    SqlAlchemyChargingSessionRepository,
)
from app.modules.charging.infrastructure.reservation_repository import SqlAlchemyVehicleRepository
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.domain.user import User
from app.shared.clock import SystemClock

router = APIRouter(tags=["Charging Sessions"])


class ChargingSessionResponse(BaseModel):
    id: UUID
    reservation_id: UUID
    owner_id: UUID
    vehicle_id: UUID
    connector_id: UUID
    status: ChargingSessionStatus
    started_at: datetime = Field(examples=["2026-07-14T12:00:00Z"])
    ended_at: datetime | None = Field(default=None, examples=["2026-07-14T13:00:00Z"])
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {"description": "Authenticated identity lacks the explicit capability"},
    404: {"description": "Resource absent or concealed"},
    409: {
        "description": "Reservation, Connector or Vehicle session conflict",
        "content": {
            "application/json": {
                "examples": {
                    "reservation": {"value": {"detail": {"code": "RESERVATION_SESSION_CONFLICT"}}},
                    "connector": {
                        "value": {"detail": {"code": "CONNECTOR_ACTIVE_SESSION_CONFLICT"}}
                    },
                    "vehicle": {"value": {"detail": {"code": "VEHICLE_ACTIVE_SESSION_CONFLICT"}}},
                }
            }
        },
    },
    422: {"description": "Activation window, infrastructure or lifecycle validation failed"},
}


def get_charging_session_service(
    db: Annotated[Session, Depends(get_db)],
) -> ChargingSessionService:
    return ChargingSessionService(
        SqlAlchemyChargingSessionRepository(db),
        get_reservation_service(db),
        SqlAlchemyVehicleRepository(db),
        SqlAlchemyChargingStationRepository(db),
        SystemClock(),
    )


def response(item: ChargingSession) -> ChargingSessionResponse:
    return ChargingSessionResponse.model_validate(item)


def map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ChargingSessionConflictError):
        return HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": "charging session exclusivity conflict"},
        )
    if isinstance(exc, (ChargingSessionNotFoundError,)):
        return HTTPException(status_code=404, detail="charging session not found")
    if isinstance(exc, ReservationNotFoundError):
        return HTTPException(status_code=404, detail="reservation not found")
    if isinstance(exc, ConnectorNotFoundError):
        return HTTPException(status_code=404, detail="connector not found")
    if isinstance(exc, VehicleNotFoundError):
        return HTTPException(status_code=404, detail="vehicle not found")
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/reservations/{reservationId}/charging-session",
    response_model=ChargingSessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
def activate_charging_session(
    reservationId: UUID,
    service: Annotated[ChargingSessionService, Depends(get_charging_session_service)],
    user: Annotated[User, Depends(current_user)],
) -> ChargingSessionResponse:
    try:
        return response(service.activate(reservationId, actor=user))
    except Exception as exc:
        if isinstance(
            exc,
            (
                ValueError,
                PermissionError,
                ReservationNotFoundError,
                ChargingSessionConflictError,
            ),
        ):
            raise map_error(exc) from exc
        raise


@router.get("/charging-sessions", response_model=list[ChargingSessionResponse])
def list_charging_sessions(
    service: Annotated[ChargingSessionService, Depends(get_charging_session_service)],
    user: Annotated[User, Depends(current_user)],
    owner_id: UUID | None = None,
    vehicle_id: UUID | None = None,
    connector_id: UUID | None = None,
    session_status: Annotated[ChargingSessionStatus | None, Query(alias="status")] = None,
    facility_id: UUID | None = None,
    station_id: UUID | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ChargingSessionResponse]:
    try:
        if started_after is not None:
            started_after = normalize_utc(started_after)
        if started_before is not None:
            started_before = normalize_utc(started_before)
        return [
            response(item)
            for item in service.list(
                actor=user,
                owner_id=owner_id,
                vehicle_id=vehicle_id,
                connector_id=connector_id,
                status=session_status,
                facility_id=facility_id,
                station_id=station_id,
                started_after=started_after,
                started_before=started_before,
                offset=offset,
                limit=limit,
            )
        ]
    except ValueError as exc:
        raise map_error(exc) from exc


@router.get("/charging-sessions/{sessionId}", response_model=ChargingSessionResponse)
def get_charging_session(
    sessionId: UUID,
    service: Annotated[ChargingSessionService, Depends(get_charging_session_service)],
    user: Annotated[User, Depends(current_user)],
) -> ChargingSessionResponse:
    try:
        return response(service.get(sessionId, actor=user))
    except ChargingSessionNotFoundError as exc:
        raise map_error(exc) from exc


@router.post(
    "/charging-sessions/{sessionId}/complete",
    response_model=ChargingSessionResponse,
    responses={403: ERROR_RESPONSES[403], 404: ERROR_RESPONSES[404], 422: ERROR_RESPONSES[422]},
)
def complete_charging_session(
    sessionId: UUID,
    service: Annotated[ChargingSessionService, Depends(get_charging_session_service)],
    user: Annotated[User, Depends(current_user)],
) -> ChargingSessionResponse:
    try:
        return response(service.complete(sessionId, actor=user))
    except (ValueError, PermissionError, ChargingSessionNotFoundError) as exc:
        raise map_error(exc) from exc


def list_params(
    session_status: Annotated[ChargingSessionStatus | None, Query(alias="status")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, object]:
    return {"status": session_status, "offset": offset, "limit": limit}


@router.get(
    "/connectors/{connectorId}/charging-sessions", response_model=list[ChargingSessionResponse]
)
def connector_charging_sessions(
    connectorId: UUID,
    filters: Annotated[dict[str, object], Depends(list_params)],
    service: Annotated[ChargingSessionService, Depends(get_charging_session_service)],
    user: Annotated[User, Depends(current_user)],
) -> list[ChargingSessionResponse]:
    try:
        return [
            response(item)
            for item in service.list_for_connector(connectorId, actor=user, **filters)
        ]
    except ConnectorNotFoundError as exc:
        raise map_error(exc) from exc


@router.get("/vehicles/{vehicleId}/charging-sessions", response_model=list[ChargingSessionResponse])
def vehicle_charging_sessions(
    vehicleId: UUID,
    filters: Annotated[dict[str, object], Depends(list_params)],
    service: Annotated[ChargingSessionService, Depends(get_charging_session_service)],
    user: Annotated[User, Depends(current_user)],
) -> list[ChargingSessionResponse]:
    try:
        return [
            response(item) for item in service.list_for_vehicle(vehicleId, actor=user, **filters)
        ]
    except VehicleNotFoundError as exc:
        raise map_error(exc) from exc
