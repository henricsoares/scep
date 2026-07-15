from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.charging.domain.reservation import normalize_utc
from app.modules.charging.infrastructure.charging_session_repository import (
    SqlAlchemyChargingSessionRepository,
)
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.domain.user import User
from app.modules.telemetry.domain import TelemetrySample, TelemetrySource
from app.modules.telemetry.infrastructure import (
    SqlAlchemyTelemetryRepository,
    TelemetryConflictError,
)
from app.modules.telemetry.service import TelemetryNotFoundError, TelemetryService
from app.shared.clock import SystemClock

router = APIRouter(tags=["Telemetry"])


class TelemetryIngestRequest(BaseModel):
    sample_id: str = Field(min_length=1, max_length=255, examples=["sample-001"])
    source: TelemetrySource = Field(examples=[TelemetrySource.SIMULATOR])
    recorded_at: datetime = Field(examples=["2026-07-14T12:05:00Z"])
    power_kw: float | None = Field(default=None, ge=0, allow_inf_nan=False, examples=[7.2])
    energy_kwh: float | None = Field(default=None, ge=0, allow_inf_nan=False, examples=[1.4])
    state_of_charge_percent: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False, examples=[55.0]
    )


class TelemetryBatchRequest(BaseModel):
    samples: list[TelemetryIngestRequest] = Field(min_length=1, max_length=1000)


class TelemetryResponse(BaseModel):
    id: UUID
    session_id: UUID
    sample_id: str
    source: TelemetrySource
    recorded_at: datetime
    received_at: datetime
    power_kw: float | None
    energy_kwh: float | None
    state_of_charge_percent: float | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"description": "Charging Session or TelemetrySample absent or concealed"},
    409: {
        "description": "The idempotency key was reused with different producer data",
        "content": {
            "application/json": {"example": {"detail": {"code": "TELEMETRY_IDEMPOTENCY_CONFLICT"}}}
        },
    },
    422: {
        "description": "Invalid measurement, timestamp, or batch",
        "content": {
            "application/json": {
                "examples": {
                    "measurement": {"value": {"detail": "power_kw must be non-negative"}},
                    "timestamp": {
                        "value": {"detail": "recorded_at is outside charging session interval"}
                    },
                }
            }
        },
    },
}


def get_telemetry_service(db: Annotated[Session, Depends(get_db)]) -> TelemetryService:
    return TelemetryService(
        SqlAlchemyTelemetryRepository(db), SqlAlchemyChargingSessionRepository(db)
    )


def _sample(payload: TelemetryIngestRequest, session_id: UUID) -> TelemetrySample:
    return TelemetrySample.create(
        session_id=session_id,
        received_at=SystemClock().now(),
        **payload.model_dump(),
    )


def _response(item: TelemetrySample) -> TelemetryResponse:
    return TelemetryResponse.model_validate(item)


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, TelemetryNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, TelemetryConflictError):
        return HTTPException(
            status_code=409,
            detail={"code": "TELEMETRY_IDEMPOTENCY_CONFLICT", "message": str(exc)},
        )
    return HTTPException(status_code=422, detail=str(exc))


@router.post(
    "/charging-sessions/{sessionId}/telemetry",
    response_model=TelemetryResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Identical retry", "model": TelemetryResponse},
        **ERROR_RESPONSES,
    },
)
def ingest_telemetry(
    sessionId: UUID,
    payload: TelemetryIngestRequest,
    response: Response,
    service: Annotated[TelemetryService, Depends(get_telemetry_service)],
    user: Annotated[User, Depends(current_user)],
) -> TelemetryResponse:
    try:
        canonical, created = service.ingest(
            sessionId, [_sample(payload, sessionId)], actor=user, batch=False
        )
        response.status_code = 201 if created else 200
        return _response(canonical[0])
    except (ValueError, TelemetryNotFoundError, TelemetryConflictError) as exc:
        raise _error(exc) from exc


@router.post(
    "/charging-sessions/{sessionId}/telemetry/batch",
    response_model=list[TelemetryResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {
            "description": "All samples were identical retries",
            "model": list[TelemetryResponse],
        },
        **ERROR_RESPONSES,
    },
)
def ingest_telemetry_batch(
    sessionId: UUID,
    payload: TelemetryBatchRequest,
    response: Response,
    service: Annotated[TelemetryService, Depends(get_telemetry_service)],
    user: Annotated[User, Depends(current_user)],
) -> list[TelemetryResponse]:
    try:
        canonical, created = service.ingest(
            sessionId,
            [_sample(item, sessionId) for item in payload.samples],
            actor=user,
            batch=True,
        )
        response.status_code = 201 if created else 200
        return [_response(item) for item in canonical]
    except (ValueError, TelemetryNotFoundError, TelemetryConflictError) as exc:
        raise _error(exc) from exc


@router.get(
    "/charging-sessions/{sessionId}/telemetry",
    response_model=list[TelemetryResponse],
    responses={404: ERROR_RESPONSES[404]},
)
def list_telemetry(
    sessionId: UUID,
    service: Annotated[TelemetryService, Depends(get_telemetry_service)],
    user: Annotated[User, Depends(current_user)],
    recorded_from: datetime | None = None,
    recorded_to: datetime | None = None,
    source: TelemetrySource | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[TelemetryResponse]:
    try:
        return [
            _response(item)
            for item in service.list(
                sessionId,
                actor=user,
                recorded_from=None if recorded_from is None else normalize_utc(recorded_from),
                recorded_to=None if recorded_to is None else normalize_utc(recorded_to),
                source=source,
                offset=offset,
                limit=limit,
            )
        ]
    except TelemetryNotFoundError as exc:
        raise _error(exc) from exc


@router.get(
    "/telemetry/{telemetryId}",
    response_model=TelemetryResponse,
    responses={404: ERROR_RESPONSES[404]},
)
def get_telemetry(
    telemetryId: UUID,
    service: Annotated[TelemetryService, Depends(get_telemetry_service)],
    user: Annotated[User, Depends(current_user)],
) -> TelemetryResponse:
    try:
        return _response(service.get(telemetryId, actor=user))
    except TelemetryNotFoundError as exc:
        raise _error(exc) from exc
