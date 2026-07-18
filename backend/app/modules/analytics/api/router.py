from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.analytics.application.models import AnalyticsQuery, Granularity
from app.modules.analytics.application.service import (
    AnalyticsAuthorizationError,
    AnalyticsNotFoundError,
    AnalyticsService,
    AnalyticsValidationError,
)
from app.modules.analytics.infrastructure.repository import AnalyticsRepository
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.domain.user import User

router = APIRouter(prefix="/analytics", tags=["Analytics"])


class AnalyticsWindow(BaseModel):
    from_: datetime = Field(alias="from", description="Inclusive analysis-window boundary")
    to: datetime = Field(description="Exclusive analysis-window boundary")
    timezone: str
    model_config = ConfigDict(populate_by_name=True)


class AnalyticsScope(BaseModel):
    facility_id: UUID | None = None
    station_id: UUID | None = None
    connector_id: UUID | None = None


class ReservationMetrics(BaseModel):
    total_reservations: int
    fulfilled_reservations: int
    cancelled_reservations: int
    late_cancelled_reservations: int
    no_show_reservations: int
    pending_reservations: int
    reservation_fulfillment_rate: float | None = Field(default=None, ge=0, le=1)
    cancellation_rate: float | None = Field(default=None, ge=0, le=1)
    late_cancellation_rate: float | None = Field(default=None, ge=0, le=1)
    no_show_rate: float | None = Field(default=None, ge=0, le=1)
    average_reservation_duration_minutes: float | None = None


class ChargingSessionMetrics(BaseModel):
    total_charging_sessions: int
    active_charging_sessions: int
    completed_charging_sessions: int
    average_session_duration_minutes: float | None = None
    average_session_start_delay_minutes: float | None = None
    on_time_start_rate: float | None = Field(default=None, ge=0, le=1)


class OccupancyMetrics(BaseModel):
    available_duration_minutes: float
    reserved_duration_minutes: float
    charging_duration_minutes: float
    effective_reserved_charging_duration_minutes: float
    unused_reserved_duration_minutes: float
    reserved_occupancy_rate: float | None = Field(default=None, ge=0, le=1)
    effective_occupancy_rate: float | None = Field(default=None, ge=0, le=1)
    reserved_time_utilization_rate: float | None = Field(default=None, ge=0, le=1)


class EnergyMetrics(BaseModel):
    total_delivered_energy_kwh: float
    sessions_with_energy_data: int
    sessions_without_energy_data: int
    average_energy_per_session_kwh: float | None = None


class SeriesItem(BaseModel):
    from_: datetime = Field(alias="from")
    to: datetime
    metrics: dict[str, int | float | None]
    model_config = ConfigDict(populate_by_name=True)


class SpecializedResponse(BaseModel):
    window: AnalyticsWindow
    scope: AnalyticsScope
    metrics: dict[str, int | float | None]
    series: list[SeriesItem] | None = None


class OverviewResponse(BaseModel):
    window: AnalyticsWindow
    scope: AnalyticsScope
    reservations: ReservationMetrics
    capacity: OccupancyMetrics
    charging_sessions: ChargingSessionMetrics
    energy: EnergyMetrics


def service(db: Annotated[Session, Depends(get_db)]) -> AnalyticsService:
    return AnalyticsService(AnalyticsRepository(db))


def common_query(
    from_: Annotated[datetime, Query(alias="from", description="Inclusive timestamp with offset")],
    to: Annotated[datetime, Query(description="Exclusive timestamp with offset")],
    facility_id: UUID | None = None,
    station_id: UUID | None = None,
    connector_id: UUID | None = None,
    timezone: str | None = None,
    granularity: Granularity | None = None,
) -> AnalyticsQuery:
    return AnalyticsQuery(from_, to, facility_id, station_id, connector_id, timezone, granularity)


def run(
    endpoint: str, query: AnalyticsQuery, analytics: AnalyticsService, user: User
) -> dict[str, Any]:
    try:
        return analytics.execute(endpoint, query, user)
    except AnalyticsValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AnalyticsAuthorizationError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except AnalyticsNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"description": "Invalid analytical query"},
    401: {"description": "Authentication required"},
    403: {"description": "Analytical scope forbidden"},
    404: {"description": "Infrastructure resource not found"},
    422: {"description": "Invalid parameter schema"},
}


@router.get(
    "/overview",
    response_model=OverviewResponse,
    responses=ERRORS,
    summary="Get an analytics overview",
    description=(
        "Platform Administrators may query all scope; Facility Operators are restricted "
        "to one assigned Facility."
    ),
)
def overview(
    query: Annotated[AnalyticsQuery, Depends(common_query)],
    analytics: Annotated[AnalyticsService, Depends(service)],
    user: Annotated[User, Depends(current_user)],
) -> dict[str, Any]:
    if query.granularity is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="overview does not support granularity",
        )
    return run("overview", query, analytics, user)


def specialized(
    endpoint: Literal["reservations", "charging-sessions", "occupancy", "energy"],
    query: AnalyticsQuery,
    analytics: AnalyticsService,
    user: User,
) -> dict[str, Any]:
    return run(endpoint, query, analytics, user)


@router.get(
    "/reservations",
    response_model=SpecializedResponse,
    responses=ERRORS,
    summary="Get reservation analytics",
)
def reservations(
    query: Annotated[AnalyticsQuery, Depends(common_query)],
    analytics: Annotated[AnalyticsService, Depends(service)],
    user: Annotated[User, Depends(current_user)],
) -> dict[str, Any]:
    return specialized("reservations", query, analytics, user)


@router.get(
    "/charging-sessions",
    response_model=SpecializedResponse,
    responses=ERRORS,
    summary="Get charging-session analytics",
)
def charging_sessions(
    query: Annotated[AnalyticsQuery, Depends(common_query)],
    analytics: Annotated[AnalyticsService, Depends(service)],
    user: Annotated[User, Depends(current_user)],
) -> dict[str, Any]:
    return specialized("charging-sessions", query, analytics, user)


@router.get(
    "/occupancy",
    response_model=SpecializedResponse,
    responses=ERRORS,
    summary="Get occupancy analytics",
)
def occupancy(
    query: Annotated[AnalyticsQuery, Depends(common_query)],
    analytics: Annotated[AnalyticsService, Depends(service)],
    user: Annotated[User, Depends(current_user)],
) -> dict[str, Any]:
    return specialized("occupancy", query, analytics, user)


@router.get(
    "/energy", response_model=SpecializedResponse, responses=ERRORS, summary="Get energy analytics"
)
def energy(
    query: Annotated[AnalyticsQuery, Depends(common_query)],
    analytics: Annotated[AnalyticsService, Depends(service)],
    user: Annotated[User, Depends(current_user)],
) -> dict[str, Any]:
    return specialized("energy", query, analytics, user)
