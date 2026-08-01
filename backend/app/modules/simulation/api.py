from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.identity.api.dependencies import require_admin
from app.modules.identity.domain.user import User
from app.modules.simulation.domain import SimulationRun, SimulationRunStatus
from app.modules.simulation.service import (
    SimulationRunActiveSessionsError,
    SimulationRunNotFoundError,
    SimulationRunService,
)
from app.shared.clock import SystemClock

router = APIRouter(tags=["Simulation Runs"])


class SimulationRunCreateRequest(BaseModel):
    logical_start_at: datetime
    logical_end_at: datetime
    facility_ids: list[UUID] = Field(default_factory=list)
    evdriver_ids: list[UUID] = Field(default_factory=list)
    external_scenario_id: str | None = Field(default=None, max_length=255)
    external_scenario_version: str | None = Field(default=None, max_length=128)
    scenario_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    simulator_version: str | None = Field(default=None, max_length=128)


class SimulationRunUpdateRequest(BaseModel):
    logical_start_at: datetime | None = None
    logical_end_at: datetime | None = None
    facility_ids: list[UUID] | None = None
    evdriver_ids: list[UUID] | None = None
    external_scenario_id: str | None = Field(default=None, max_length=255)
    external_scenario_version: str | None = Field(default=None, max_length=128)
    scenario_sha256: str | None = Field(default=None, min_length=64, max_length=64)
    simulator_version: str | None = Field(default=None, max_length=128)


class SimulationRunResponse(BaseModel):
    id: UUID
    status: SimulationRunStatus
    logical_start_at: datetime
    logical_end_at: datetime
    last_accepted_simulated_at: datetime | None
    facility_ids: list[UUID]
    evdriver_ids: list[UUID]
    external_scenario_id: str | None
    external_scenario_version: str | None
    scenario_sha256: str | None
    simulator_version: str | None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class SimulationRunStartResponse(BaseModel):
    simulation_run: SimulationRunResponse
    simulation_token: str


class BootstrapRunResponse(BaseModel):
    id: UUID
    status: SimulationRunStatus
    logical_start_at: datetime
    logical_end_at: datetime


class SimulationBootstrapResponse(BaseModel):
    bootstrap_version: str = "1.0"
    api_version: str = "1"
    generated_at: datetime
    simulation_run: BootstrapRunResponse
    authorized_facility_ids: list[UUID]
    authorized_evdriver_ids: list[UUID]


ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"description": "Authentication required"},
    403: {"description": "PlatformAdministrator Role required"},
    404: {"description": "SimulationRun not found"},
    409: {"description": "Invalid SimulationRun lifecycle transition"},
    422: {"description": "Invalid SimulationRun configuration"},
}


def get_simulation_run_service(
    db: Annotated[Session, Depends(get_db)],
) -> SimulationRunService:
    return SimulationRunService(db, SystemClock())


def _response(item: SimulationRun) -> SimulationRunResponse:
    return SimulationRunResponse(
        id=item.id,
        status=item.status,
        logical_start_at=item.logical_start_at,
        logical_end_at=item.logical_end_at,
        last_accepted_simulated_at=item.last_accepted_simulated_at,
        facility_ids=list(item.facility_ids),
        evdriver_ids=list(item.evdriver_ids),
        external_scenario_id=item.external_scenario_id,
        external_scenario_version=item.external_scenario_version,
        scenario_sha256=item.scenario_sha256,
        simulator_version=item.simulator_version,
        created_by=item.created_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
        started_at=item.started_at,
        completed_at=item.completed_at,
        cancelled_at=item.cancelled_at,
    )


def _error(exc: Exception) -> HTTPException:
    if isinstance(exc, SimulationRunNotFoundError):
        return HTTPException(
            status_code=404,
            detail={"code": "SIMULATION_RUN_NOT_FOUND", "message": str(exc)},
        )
    if isinstance(exc, SimulationRunActiveSessionsError):
        return HTTPException(
            status_code=409,
            detail={"code": "SIMULATION_ACTIVE_SESSIONS_EXIST", "message": str(exc)},
        )
    message = str(exc)
    lifecycle = any(word in message for word in ("only DRAFT", "only RUNNING", "CANCELLED"))
    return HTTPException(
        status_code=409 if lifecycle else 422,
        detail={"code": "SIMULATION_RUN_INVALID", "message": message},
    )


@router.post(
    "/simulation-runs",
    response_model=SimulationRunResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
)
def create_simulation_run(
    payload: SimulationRunCreateRequest,
    service: Annotated[SimulationRunService, Depends(get_simulation_run_service)],
    admin: Annotated[User, Depends(require_admin)],
) -> SimulationRunResponse:
    try:
        return _response(service.create(created_by=admin.id, **payload.model_dump()))
    except ValueError as exc:
        raise _error(exc) from exc


@router.get(
    "/simulation-runs/{simulationRunId}",
    response_model=SimulationRunResponse,
    responses={code: ERRORS[code] for code in (401, 403, 404)},
)
def get_simulation_run(
    simulationRunId: UUID,
    service: Annotated[SimulationRunService, Depends(get_simulation_run_service)],
    _admin: Annotated[User, Depends(require_admin)],
) -> SimulationRunResponse:
    try:
        return _response(service.get(simulationRunId))
    except SimulationRunNotFoundError as exc:
        raise _error(exc) from exc


@router.patch(
    "/simulation-runs/{simulationRunId}",
    response_model=SimulationRunResponse,
    responses=ERRORS,
)
def update_simulation_run(
    simulationRunId: UUID,
    payload: SimulationRunUpdateRequest,
    service: Annotated[SimulationRunService, Depends(get_simulation_run_service)],
    _admin: Annotated[User, Depends(require_admin)],
) -> SimulationRunResponse:
    try:
        current = service.get(simulationRunId)
        changes = payload.model_fields_set
        return _response(
            service.update(
                simulationRunId,
                logical_start_at=payload.logical_start_at,
                logical_end_at=payload.logical_end_at,
                facility_ids=payload.facility_ids,
                evdriver_ids=payload.evdriver_ids,
                external_scenario_id=(
                    payload.external_scenario_id
                    if "external_scenario_id" in changes
                    else current.external_scenario_id
                ),
                external_scenario_version=(
                    payload.external_scenario_version
                    if "external_scenario_version" in changes
                    else current.external_scenario_version
                ),
                scenario_sha256=(
                    payload.scenario_sha256
                    if "scenario_sha256" in changes
                    else current.scenario_sha256
                ),
                simulator_version=(
                    payload.simulator_version
                    if "simulator_version" in changes
                    else current.simulator_version
                ),
            )
        )
    except (ValueError, SimulationRunNotFoundError) as exc:
        raise _error(exc) from exc


@router.post(
    "/simulation-runs/{simulationRunId}/start",
    response_model=SimulationRunStartResponse,
    responses=ERRORS,
)
def start_simulation_run(
    simulationRunId: UUID,
    service: Annotated[SimulationRunService, Depends(get_simulation_run_service)],
    _admin: Annotated[User, Depends(require_admin)],
) -> SimulationRunStartResponse:
    try:
        item, token = service.start(simulationRunId)
        return SimulationRunStartResponse(simulation_run=_response(item), simulation_token=token)
    except (ValueError, SimulationRunNotFoundError) as exc:
        raise _error(exc) from exc


@router.post(
    "/simulation-runs/{simulationRunId}/complete",
    response_model=SimulationRunResponse,
    responses=ERRORS,
)
def complete_simulation_run(
    simulationRunId: UUID,
    service: Annotated[SimulationRunService, Depends(get_simulation_run_service)],
    _admin: Annotated[User, Depends(require_admin)],
) -> SimulationRunResponse:
    try:
        return _response(service.complete(simulationRunId))
    except (ValueError, SimulationRunNotFoundError, SimulationRunActiveSessionsError) as exc:
        raise _error(exc) from exc


@router.post(
    "/simulation-runs/{simulationRunId}/cancel",
    response_model=SimulationRunResponse,
    responses=ERRORS,
)
def cancel_simulation_run(
    simulationRunId: UUID,
    service: Annotated[SimulationRunService, Depends(get_simulation_run_service)],
    _admin: Annotated[User, Depends(require_admin)],
) -> SimulationRunResponse:
    try:
        return _response(service.cancel(simulationRunId))
    except (ValueError, SimulationRunNotFoundError) as exc:
        raise _error(exc) from exc


@router.get(
    "/simulation-runs/{simulationRunId}/bootstrap",
    response_model=SimulationBootstrapResponse,
    responses={code: ERRORS[code] for code in (401, 403, 404)},
)
def get_simulation_bootstrap(
    simulationRunId: UUID,
    service: Annotated[SimulationRunService, Depends(get_simulation_run_service)],
    _admin: Annotated[User, Depends(require_admin)],
) -> SimulationBootstrapResponse:
    try:
        item = service.get(simulationRunId)
    except SimulationRunNotFoundError as exc:
        raise _error(exc) from exc
    return SimulationBootstrapResponse(
        generated_at=SystemClock().now(),
        simulation_run=BootstrapRunResponse(
            id=item.id,
            status=item.status,
            logical_start_at=item.logical_start_at,
            logical_end_at=item.logical_end_at,
        ),
        authorized_facility_ids=list(item.facility_ids),
        authorized_evdriver_ids=list(item.evdriver_ids),
    )
