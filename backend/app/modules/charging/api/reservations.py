from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.charging.application.facility_service import FacilityNotFoundError
from app.modules.charging.application.reservation_service import (
    ReservationNotFoundError,
    ReservationService,
    SchedulingConflictError,
)
from app.modules.charging.application.station_service import (
    ChargingStationNotFoundError,
    ConnectorNotFoundError,
)
from app.modules.charging.application.vehicle_service import VehicleNotFoundError
from app.modules.charging.domain.reservation import Reservation, ReservationStatus, normalize_utc
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.reservation_repository import (
    SqlAlchemyReservationRepository,
    SqlAlchemyVehicleRepository,
)
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.domain.user import User
from app.shared.clock import SystemClock

router = APIRouter(tags=["Reservations"])


class ReservationCreatePayload(BaseModel):
    vehicle_id: UUID
    connector_id: UUID
    start_at: datetime = Field(examples=["2026-07-13T09:00:00-03:00"])
    end_at: datetime = Field(examples=["2026-07-13T10:00:00-03:00"])
    owner_id: UUID | None = Field(default=None, description="Platform Administrator only")
    model_config = ConfigDict(extra="forbid")


class ReservationPatchPayload(BaseModel):
    vehicle_id: UUID | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "ReservationPatchPayload":
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be null")
        return self


class ReservationResponse(BaseModel):
    id: UUID
    owner_id: UUID
    vehicle_id: UUID
    connector_id: UUID
    start_at: datetime
    end_at: datetime
    status: ReservationStatus
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    late_cancelled_at: datetime | None
    no_show_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class WarningResponse(BaseModel):
    code: str
    message: str


class ReservationEnvelope(BaseModel):
    reservation: ReservationResponse
    warnings: list[WarningResponse]


def get_reservation_service(db: Annotated[Session, Depends(get_db)]) -> ReservationService:
    return ReservationService(
        SqlAlchemyReservationRepository(db),
        SqlAlchemyVehicleRepository(db),
        SqlAlchemyChargingStationRepository(db),
        SqlAlchemyFacilityRepository(db),
        SystemClock(),
    )


def response(item: Reservation) -> ReservationResponse:
    return ReservationResponse.model_validate(item)


def envelope(item: Reservation, warning: str | None = None) -> ReservationEnvelope:
    messages = {
        "BACK_TO_BACK_RESERVATION": (
            "Another blocking reservation meets this reservation at its boundary."
        ),
        "LATE_CANCELLATION": "The reservation was cancelled after the normal cancellation cutoff.",
    }
    warnings = [] if warning is None else [WarningResponse(code=warning, message=messages[warning])]
    return ReservationEnvelope(reservation=response(item), warnings=warnings)


def map_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SchedulingConflictError):
        return HTTPException(
            status_code=409,
            detail={
                "code": exc.code,
                "message": "reservation interval conflicts with an existing blocking reservation",
            },
        )
    if isinstance(exc, ReservationNotFoundError):
        return HTTPException(status_code=404, detail="reservation not found")
    if isinstance(exc, VehicleNotFoundError):
        return HTTPException(status_code=404, detail="vehicle not found")
    if isinstance(exc, ConnectorNotFoundError):
        return HTTPException(status_code=404, detail="connector not found")
    if isinstance(exc, ChargingStationNotFoundError):
        return HTTPException(status_code=404, detail="charging station not found")
    if isinstance(exc, FacilityNotFoundError):
        return HTTPException(status_code=404, detail="facility not found")
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/reservations",
    response_model=ReservationEnvelope,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Connector or Vehicle scheduling conflict"}},
)
def create_reservation(
    payload: ReservationCreatePayload,
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    user: Annotated[User, Depends(current_user)],
) -> ReservationEnvelope:
    try:
        item, adjacent = service.create(actor=user, **payload.model_dump())
        return envelope(item, "BACK_TO_BACK_RESERVATION" if adjacent else None)
    except (
        ValueError,
        PermissionError,
        SchedulingConflictError,
        VehicleNotFoundError,
        ConnectorNotFoundError,
        ChargingStationNotFoundError,
        FacilityNotFoundError,
    ) as exc:
        raise map_error(exc) from exc


@router.get("/reservations", response_model=list[ReservationResponse])
def list_reservations(
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    user: Annotated[User, Depends(current_user)],
    owner_id: UUID | None = None,
    vehicle_id: UUID | None = None,
    connector_id: UUID | None = None,
    reservation_status: Annotated[ReservationStatus | None, Query(alias="status")] = None,
    facility_id: UUID | None = None,
    station_id: UUID | None = None,
    starts_before: datetime | None = None,
    ends_after: datetime | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ReservationResponse]:
    try:
        if starts_before is not None:
            starts_before = normalize_utc(starts_before)
        if ends_after is not None:
            ends_after = normalize_utc(ends_after)
        items = service.list(
            actor=user,
            owner_id=owner_id,
            vehicle_id=vehicle_id,
            connector_id=connector_id,
            status=reservation_status,
            facility_id=facility_id,
            station_id=station_id,
            starts_before=starts_before,
            ends_after=ends_after,
            offset=offset,
            limit=limit,
        )
        return [response(item) for item in items]
    except ValueError as exc:
        raise map_error(exc) from exc


@router.get("/reservations/{reservationId}", response_model=ReservationResponse)
def get_reservation(
    reservationId: UUID,
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    user: Annotated[User, Depends(current_user)],
) -> ReservationResponse:
    try:
        return response(service.get(reservationId, actor=user))
    except ReservationNotFoundError as exc:
        raise map_error(exc) from exc


@router.patch("/reservations/{reservationId}", response_model=ReservationEnvelope)
def patch_reservation(
    reservationId: UUID,
    payload: ReservationPatchPayload,
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    user: Annotated[User, Depends(current_user)],
) -> ReservationEnvelope:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="at least one field is required")
    try:
        item, adjacent = service.reschedule(
            reservationId,
            actor=user,
            vehicle_id=changes.get("vehicle_id"),
            start_at=changes.get("start_at"),
            end_at=changes.get("end_at"),
        )
        return envelope(item, "BACK_TO_BACK_RESERVATION" if adjacent else None)
    except (
        ValueError,
        PermissionError,
        ReservationNotFoundError,
        SchedulingConflictError,
        VehicleNotFoundError,
        ConnectorNotFoundError,
        ChargingStationNotFoundError,
        FacilityNotFoundError,
    ) as exc:
        raise map_error(exc) from exc


@router.post("/reservations/{reservationId}/cancel", response_model=ReservationEnvelope)
def cancel_reservation(
    reservationId: UUID,
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    user: Annotated[User, Depends(current_user)],
) -> ReservationEnvelope:
    try:
        item = service.cancel(reservationId, actor=user)
        warning = "LATE_CANCELLATION" if item.status == ReservationStatus.LATE_CANCELLED else None
        return envelope(item, warning)
    except (ValueError, PermissionError, ReservationNotFoundError) as exc:
        raise map_error(exc) from exc


@router.get("/connectors/{connectorId}/reservations", response_model=list[ReservationResponse])
def connector_calendar(
    connectorId: UUID,
    service: Annotated[ReservationService, Depends(get_reservation_service)],
    user: Annotated[User, Depends(current_user)],
    reservation_status: Annotated[ReservationStatus | None, Query(alias="status")] = None,
    starts_before: datetime | None = None,
    ends_after: datetime | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ReservationResponse]:
    if service.stations.get_connector(connectorId) is None:
        raise HTTPException(status_code=404, detail="connector not found")
    try:
        if starts_before is not None:
            starts_before = normalize_utc(starts_before)
        if ends_after is not None:
            ends_after = normalize_utc(ends_after)
        return [
            response(item)
            for item in service.list(
                actor=user,
                connector_id=connectorId,
                status=reservation_status,
                starts_before=starts_before,
                ends_after=ends_after,
                offset=offset,
                limit=limit,
            )
        ]
    except ValueError as exc:
        raise map_error(exc) from exc
