from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.charging.application.vehicle_service import VehicleNotFoundError, VehicleService
from app.modules.charging.domain.vehicle import Vehicle, VehicleStatus
from app.modules.charging.infrastructure.reservation_repository import SqlAlchemyVehicleRepository
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.domain.user import User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from app.shared.clock import SystemClock

router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


class VehicleCreatePayload(BaseModel):
    display_name: str = Field(min_length=1, max_length=255, examples=["Primary EV"])
    owner_id: UUID | None = Field(
        default=None,
        description="Platform Administrator only; defaults to the authenticated identity",
    )
    model_config = ConfigDict(extra="forbid")


class VehiclePatchPayload(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    status: VehicleStatus | None = None
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def reject_explicit_nulls(self) -> "VehiclePatchPayload":
        for field_name in self.model_fields_set:
            if getattr(self, field_name) is None:
                raise ValueError(f"{field_name} must not be null")
        return self


class VehicleResponse(BaseModel):
    id: UUID
    owner_id: UUID
    display_name: str
    status: VehicleStatus
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


def get_vehicle_service(db: Annotated[Session, Depends(get_db)]) -> VehicleService:
    return VehicleService(
        SqlAlchemyVehicleRepository(db), SqlAlchemyUserRepository(db), SystemClock()
    )


def response(item: Vehicle) -> VehicleResponse:
    return VehicleResponse.model_validate(item)


@router.post("", response_model=VehicleResponse, status_code=status.HTTP_201_CREATED)
def create_vehicle(
    payload: VehicleCreatePayload,
    service: Annotated[VehicleService, Depends(get_vehicle_service)],
    user: Annotated[User, Depends(current_user)],
) -> VehicleResponse:
    try:
        return response(service.create(actor=user, **payload.model_dump()))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("", response_model=list[VehicleResponse])
def list_vehicles(
    service: Annotated[VehicleService, Depends(get_vehicle_service)],
    user: Annotated[User, Depends(current_user)],
    owner_id: UUID | None = None,
    vehicle_status: Annotated[VehicleStatus | None, Query(alias="status")] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[VehicleResponse]:
    return [
        response(item)
        for item in service.list(
            actor=user, owner_id=owner_id, status=vehicle_status, offset=offset, limit=limit
        )
    ]


@router.get("/{vehicleId}", response_model=VehicleResponse)
def get_vehicle(
    vehicleId: UUID,
    service: Annotated[VehicleService, Depends(get_vehicle_service)],
    user: Annotated[User, Depends(current_user)],
) -> VehicleResponse:
    try:
        return response(service.get(vehicleId, actor=user))
    except VehicleNotFoundError as exc:
        raise HTTPException(status_code=404, detail="vehicle not found") from exc


@router.patch("/{vehicleId}", response_model=VehicleResponse)
def patch_vehicle(
    vehicleId: UUID,
    payload: VehiclePatchPayload,
    service: Annotated[VehicleService, Depends(get_vehicle_service)],
    user: Annotated[User, Depends(current_user)],
) -> VehicleResponse:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="at least one field is required")
    try:
        return response(
            service.update(
                vehicleId,
                actor=user,
                display_name=changes.get("display_name"),
                status=changes.get("status"),
            )
        )
    except VehicleNotFoundError as exc:
        raise HTTPException(status_code=404, detail="vehicle not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
