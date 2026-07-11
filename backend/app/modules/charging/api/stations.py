from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.charging.application.station_service import (
    ChargingStationNotFoundError,
    ChargingStationSerialNumberAlreadyExistsError,
    ChargingStationService,
    ConnectorNotFoundError,
    FacilityUnavailableError,
)
from app.modules.charging.domain.facility import Facility
from app.modules.charging.domain.station import (
    ChargingStation,
    ChargingStationStatus,
    Connector,
    ConnectorStatus,
    ConnectorType,
)
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.application.authorization import can_manage_facility, can_read_facility
from app.modules.identity.domain.user import User

router = APIRouter(tags=["Charging Stations"])


class ConnectorPayload(BaseModel):
    connector_type: ConnectorType = Field(examples=[ConnectorType.CCS2])
    maximum_power_kw: float = Field(gt=0, examples=[50.0])
    status: ConnectorStatus = Field(
        default=ConnectorStatus.AVAILABLE, examples=[ConnectorStatus.AVAILABLE]
    )


class ConnectorResponse(ConnectorPayload):
    id: UUID
    charging_station_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class StationCreatePayload(BaseModel):
    name: str = Field(min_length=1, examples=["Station A"])
    description: str | None = Field(default=None, examples=["North lot charger"])
    serial_number: str = Field(min_length=1, examples=["SN-004-001"])
    manufacturer: str | None = Field(default=None, examples=["SCEP Chargers"])
    model: str | None = Field(default=None, examples=["SC-50"])
    maximum_power_kw: float = Field(gt=0, examples=[50.0])
    status: ChargingStationStatus = Field(
        default=ChargingStationStatus.ACTIVE, examples=[ChargingStationStatus.ACTIVE]
    )
    connectors: list[ConnectorPayload] = Field(min_length=1)


class StationPatchPayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, examples=["Station A Updated"])
    description: str | None = Field(default=None, examples=["Updated metadata"])
    status: ChargingStationStatus | None = Field(
        default=None, examples=[ChargingStationStatus.UNDER_MAINTENANCE]
    )
    model_config = ConfigDict(extra="forbid")


class ConnectorStatusPayload(BaseModel):
    status: ConnectorStatus = Field(examples=[ConnectorStatus.OUT_OF_SERVICE])
    model_config = ConfigDict(extra="forbid")


class StationResponse(BaseModel):
    id: UUID
    facility_id: UUID
    name: str
    description: str | None
    serial_number: str
    manufacturer: str | None
    model: str | None
    maximum_power_kw: float
    status: ChargingStationStatus
    connectors: list[ConnectorResponse]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


def get_station_service(db: Annotated[Session, Depends(get_db)]) -> ChargingStationService:
    return ChargingStationService(
        SqlAlchemyChargingStationRepository(db), SqlAlchemyFacilityRepository(db)
    )


def _facility_for_station(service: ChargingStationService, station_id: UUID) -> Facility | None:
    return service.facility_repository.get(service.get_station(station_id).facility_id)


def _facility_for_connector(service: ChargingStationService, connector_id: UUID) -> Facility | None:
    connector = service.station_repository.get_connector(connector_id)
    if connector is None:
        raise ConnectorNotFoundError("connector not found")
    return _facility_for_station(service, connector.charging_station_id)


def station_response(station: ChargingStation) -> StationResponse:
    return StationResponse(
        **{
            **station.__dict__,
            "connectors": [ConnectorResponse(**c.__dict__) for c in station.connectors],
        }
    )


def connector_response(connector: Connector) -> ConnectorResponse:
    return ConnectorResponse(**connector.__dict__)


@router.post(
    "/facilities/{facility_id}/stations",
    response_model=StationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a charging station in a facility",
)
def create_station(
    facility_id: UUID,
    payload: StationCreatePayload,
    service: Annotated[ChargingStationService, Depends(get_station_service)],
    user: Annotated[User, Depends(current_user)],
) -> StationResponse:
    if not can_manage_facility(user, facility_id):
        raise HTTPException(status_code=404, detail="facility not found")
    try:
        connectors = [(c.connector_type, c.maximum_power_kw, c.status) for c in payload.connectors]
        return station_response(
            service.create_station(
                facility_id=facility_id,
                connectors=connectors,
                **payload.model_dump(exclude={"connectors"}),
            )
        )
    except ChargingStationSerialNumberAlreadyExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ChargingStationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (FacilityUnavailableError, ValueError, IntegrityError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(
    "/facilities/{facility_id}/stations",
    response_model=list[StationResponse],
    summary="List charging stations for a facility",
)
def list_stations(
    facility_id: UUID,
    service: Annotated[ChargingStationService, Depends(get_station_service)],
    user: Annotated[User, Depends(current_user)],
) -> list[StationResponse]:
    try:
        facility = service.facility_repository.get(facility_id)
        if facility is None or not can_read_facility(user, facility):
            raise HTTPException(status_code=404, detail="facility not found")
        return [station_response(s) for s in service.list_by_facility(facility_id)]
    except ChargingStationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/stations/{station_id}",
    response_model=StationResponse,
    summary="Get a charging station with connectors",
)
def get_station(
    station_id: UUID,
    service: Annotated[ChargingStationService, Depends(get_station_service)],
    user: Annotated[User, Depends(current_user)],
) -> StationResponse:
    try:
        facility = _facility_for_station(service, station_id)
        if facility is None or not can_read_facility(user, facility):
            raise HTTPException(status_code=404, detail="station not found")
        return station_response(service.get_station(station_id))
    except ChargingStationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch(
    "/stations/{station_id}",
    response_model=StationResponse,
    summary="Update charging station metadata and status",
)
def patch_station(
    station_id: UUID,
    payload: StationPatchPayload,
    service: Annotated[ChargingStationService, Depends(get_station_service)],
    user: Annotated[User, Depends(current_user)],
) -> StationResponse:
    try:
        facility = _facility_for_station(service, station_id)
        if facility is None or not can_manage_facility(user, facility.id):
            raise HTTPException(status_code=404, detail="station not found")
        data = payload.model_dump(exclude_unset=True)
        if not data:
            raise ValueError("empty payload")
        return station_response(service.update_station(station_id, **data))
    except ChargingStationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/stations/{station_id}/connectors",
    response_model=ConnectorResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a connector to a charging station",
)
def add_connector(
    station_id: UUID,
    payload: ConnectorPayload,
    service: Annotated[ChargingStationService, Depends(get_station_service)],
    user: Annotated[User, Depends(current_user)],
) -> ConnectorResponse:
    try:
        facility = _facility_for_station(service, station_id)
        if facility is None or not can_manage_facility(user, facility.id):
            raise HTTPException(status_code=404, detail="station not found")
        return connector_response(service.add_connector(station_id, **payload.model_dump()))
    except ChargingStationNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, IntegrityError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch(
    "/connectors/{connector_id}/status",
    response_model=ConnectorResponse,
    summary="Update connector status",
)
def patch_connector_status(
    connector_id: UUID,
    payload: ConnectorStatusPayload,
    service: Annotated[ChargingStationService, Depends(get_station_service)],
    user: Annotated[User, Depends(current_user)],
) -> ConnectorResponse:
    try:
        facility = _facility_for_connector(service, connector_id)
        if facility is None or not can_manage_facility(user, facility.id):
            raise HTTPException(status_code=404, detail="connector not found")
        return connector_response(
            service.update_connector_status(connector_id, **payload.model_dump())
        )
    except ConnectorNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
