from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.charging.application.facility_service import (
    FacilityNameAlreadyExistsError,
    FacilityNotFoundError,
    FacilityService,
)
from app.modules.charging.domain.facility import Facility, FacilityStatus, FacilityType
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository

router = APIRouter(prefix="/facilities", tags=["Facilities"])


class FacilityPayload(BaseModel):
    name: str = Field(min_length=1, examples=["North Campus"])
    facility_type: FacilityType = Field(examples=[FacilityType.UNIVERSITY])
    timezone: str = Field(examples=["America/New_York"])
    country: str = Field(min_length=1, examples=["United States"])
    city: str = Field(min_length=1, examples=["New York"])
    address: str = Field(min_length=1, examples=["123 Main St"])
    latitude: float | None = Field(default=None, ge=-90, le=90, examples=[40.7128])
    longitude: float | None = Field(default=None, ge=-180, le=180, examples=[-74.006])
    operating_hours: dict[str, Any] | None = Field(
        default=None,
        examples=[{"monday": {"opens": "08:00", "closes": "22:00"}}],
    )
    status: FacilityStatus = Field(default=FacilityStatus.ACTIVE, examples=[FacilityStatus.ACTIVE])


class FacilityResponse(FacilityPayload):
    id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


def get_facility_service(db: Annotated[Session, Depends(get_db)]) -> FacilityService:
    return FacilityService(SqlAlchemyFacilityRepository(db))


def to_response(facility: Facility) -> FacilityResponse:
    return FacilityResponse(**facility.__dict__)


def conflict_response(exc: Exception) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "",
    response_model=FacilityResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a facility",
)
def create_facility(
    payload: FacilityPayload, service: Annotated[FacilityService, Depends(get_facility_service)]
) -> FacilityResponse:
    try:
        facility = service.create_facility(**payload.model_dump())
    except FacilityNameAlreadyExistsError as exc:
        raise conflict_response(exc) from exc
    except (ValueError, IntegrityError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return to_response(facility)


@router.get("", response_model=list[FacilityResponse], summary="List facilities")
def list_facilities(
    service: Annotated[FacilityService, Depends(get_facility_service)],
) -> list[FacilityResponse]:
    return [to_response(facility) for facility in service.list_facilities()]


@router.get(
    "/{facilityId}",
    response_model=FacilityResponse,
    summary="Get a facility by identifier",
)
def get_facility(
    facilityId: UUID, service: Annotated[FacilityService, Depends(get_facility_service)]
) -> FacilityResponse:
    try:
        return to_response(service.get_facility(facilityId))
    except FacilityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="facility not found"
        ) from exc


@router.put(
    "/{facilityId}",
    response_model=FacilityResponse,
    summary="Update a facility",
)
def update_facility(
    facilityId: UUID,
    payload: FacilityPayload,
    service: Annotated[FacilityService, Depends(get_facility_service)],
) -> FacilityResponse:
    try:
        return to_response(service.update_facility(facilityId, **payload.model_dump()))
    except FacilityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="facility not found"
        ) from exc
    except FacilityNameAlreadyExistsError as exc:
        raise conflict_response(exc) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.delete(
    "/{facilityId}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a facility",
)
def delete_facility(
    facilityId: UUID, service: Annotated[FacilityService, Depends(get_facility_service)]
) -> None:
    try:
        service.delete_facility(facilityId)
    except FacilityNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="facility not found"
        ) from exc
