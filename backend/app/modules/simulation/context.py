from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.infrastructure.database import get_db
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.domain.user import User
from app.modules.simulation.domain import SimulationRunStatus, utc
from app.modules.simulation.infrastructure import (
    SimulationRunEvDriverModel,
    SimulationRunModel,
)
from app.modules.simulation.metrics import simulation_rejections_total
from app.modules.simulation.security import verify_run_credential
from app.shared.clock import FixedClock

SIMULATION_HEADERS = {
    "x-simulation-run-id",
    "x-simulated-at",
    "x-simulation-event-id",
    "x-simulation-token",
}
SIMULATED_PATHS = tuple(
    re.compile(pattern)
    for pattern in (
        r"^/reservations$",
        r"^/reservations/[^/]+/cancel$",
        r"^/reservations/[^/]+/charging-session$",
        r"^/charging-sessions/[^/]+/complete$",
        r"^/charging-sessions/[^/]+/telemetry$",
        r"^/charging-sessions/[^/]+/telemetry/batch$",
    )
)


class SimulationContextAllowlistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = SIMULATION_HEADERS.intersection(request.headers.keys())
        supported = request.method == "POST" and any(
            pattern.fullmatch(request.url.path) for pattern in SIMULATED_PATHS
        )
        if supplied and not supported:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": {
                        "code": "SIMULATION_CONTEXT_NOT_SUPPORTED",
                        "message": "simulation context is not supported on this endpoint",
                    }
                },
            )
        return await call_next(request)


@dataclass(frozen=True, slots=True)
class SimulationRequestContext:
    simulation_run_id: UUID
    simulation_event_id: UUID
    simulated_at: datetime
    evdriver_id: UUID

    @property
    def clock(self) -> FixedClock:
        return FixedClock(self.simulated_at)


def optional_simulation_context(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
    run_id: Annotated[
        str | None,
        Header(
            alias="X-Simulation-Run-Id",
            description=(
                "Optional SimulationRun UUID; all four simulation headers are required together"
            ),
        ),
    ] = None,
    simulated_at: Annotated[
        str | None,
        Header(
            alias="X-Simulated-At",
            description=(
                "RFC3339 logical time with explicit offset for an authorized simulated mutation"
            ),
        ),
    ] = None,
    event_id: Annotated[
        str | None,
        Header(
            alias="X-Simulation-Event-Id",
            description="Stable event UUID reused unchanged for technical retry",
        ),
    ] = None,
    token: Annotated[
        str | None,
        Header(
            alias="X-Simulation-Token",
            description="Run-scoped secret issued once when the SimulationRun starts",
        ),
    ] = None,
) -> SimulationRequestContext | None:
    values = (run_id, simulated_at, event_id, token)
    if all(value is None for value in values):
        return None
    if any(not value for value in values):
        raise _error(400, "SIMULATION_CONTEXT_INCOMPLETE", "all simulation headers are required")
    assert run_id is not None and simulated_at is not None and event_id is not None and token
    try:
        parsed_run_id = UUID(run_id)
        parsed_event_id = UUID(event_id)
        parsed_time = utc(datetime.fromisoformat(simulated_at.replace("Z", "+00:00")))
    except ValueError as exc:
        raise _error(422, "SIMULATION_CONTEXT_INCOMPLETE", "invalid simulation header") from exc
    run = db.get(SimulationRunModel, parsed_run_id)
    if run is None:
        raise _error(401, "SIMULATION_RUN_CREDENTIAL_INVALID", "invalid simulation context")
    if run.status != SimulationRunStatus.RUNNING.value:
        raise _error(409, "SIMULATION_RUN_NOT_RUNNING", "simulation run is not RUNNING")
    if run.credential_hash is None or not verify_run_credential(token, run.credential_hash):
        raise _error(401, "SIMULATION_RUN_CREDENTIAL_INVALID", "invalid simulation context")
    authorized = db.scalar(
        select(SimulationRunEvDriverModel.user_id).where(
            SimulationRunEvDriverModel.simulation_run_id == parsed_run_id,
            SimulationRunEvDriverModel.user_id == user.id,
        )
    )
    if authorized is None:
        raise _error(403, "SIMULATION_DRIVER_NOT_AUTHORIZED", "driver is not authorized")
    start = _stored_utc(run.logical_start_at)
    end = _stored_utc(run.logical_end_at)
    if not start <= parsed_time <= end:
        raise _error(422, "SIMULATION_TIME_OUTSIDE_WINDOW", "simulated time is outside run window")
    return SimulationRequestContext(parsed_run_id, parsed_event_id, parsed_time, user.id)


def _error(status_code: int, code: str, message: str) -> HTTPException:
    simulation_rejections_total.labels(code).inc()
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _stored_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
