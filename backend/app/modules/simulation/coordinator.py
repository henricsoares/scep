from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from time import perf_counter
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.modules.simulation.context import SimulationRequestContext
from app.modules.simulation.domain import SimulationRunStatus
from app.modules.simulation.infrastructure import SimulationRunRepository
from app.modules.simulation.metrics import (
    simulation_operations_total,
    simulation_rejections_total,
    simulation_transaction_duration_seconds,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SimulationMutationResult:
    response_status: int
    response_snapshot: dict[str, Any]
    resource_type: str | None
    resource_id: UUID | None
    replayed: bool = False


class SimulationMutationCoordinator:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.runs = SimulationRunRepository(session)

    def execute(
        self,
        *,
        context: SimulationRequestContext,
        operation: str,
        canonical_content: dict[str, Any],
        facility_id: UUID,
        action: Callable[[], SimulationMutationResult],
    ) -> SimulationMutationResult:
        started = perf_counter()
        digest = canonical_request_digest(
            operation=operation,
            content=canonical_content,
            context=context,
        )
        try:
            run = self.runs.get(context.simulation_run_id, for_update=True)
            if run is None or run.status != SimulationRunStatus.RUNNING:
                raise _error(409, "SIMULATION_RUN_NOT_RUNNING", "simulation run is not RUNNING")
            receipt = self.runs.receipt(run.id, operation, context.simulation_event_id)
            if receipt is not None:
                if receipt.request_sha256 != digest:
                    simulation_operations_total.labels(operation, "idempotency_conflict").inc()
                    raise _error(
                        409,
                        "SIMULATION_EVENT_IDEMPOTENCY_CONFLICT",
                        "simulation event ID was reused with different content",
                    )
                result = SimulationMutationResult(
                    response_status=receipt.response_status,
                    response_snapshot=dict(receipt.response_snapshot),
                    resource_type=receipt.resource_type,
                    resource_id=receipt.resource_id,
                    replayed=True,
                )
                self.session.rollback()
                simulation_operations_total.labels(operation, "idempotent_replay").inc()
                self._log(context, operation, result)
                return result
            if facility_id not in run.facility_ids:
                raise _error(
                    403,
                    "SIMULATION_FACILITY_NOT_AUTHORIZED",
                    "Facility is not authorized for this run",
                )
            if not run.logical_start_at <= context.simulated_at <= run.logical_end_at:
                raise _error(
                    422,
                    "SIMULATION_TIME_OUTSIDE_WINDOW",
                    "simulated time is outside run window",
                )
            if (
                run.last_accepted_simulated_at is not None
                and context.simulated_at < run.last_accepted_simulated_at
            ):
                raise _error(
                    409,
                    "SIMULATION_TIME_REGRESSION",
                    "simulated time is older than the last accepted event",
                )
            result = action()
            self.runs.add_receipt(
                run_id=run.id,
                event_id=context.simulation_event_id,
                operation=operation,
                actor_id=context.evdriver_id,
                simulated_at=context.simulated_at,
                request_sha256=digest,
                resource_type=result.resource_type,
                resource_id=result.resource_id,
                response_status=result.response_status,
                response_snapshot=result.response_snapshot,
                created_at=datetime.now(UTC),
            )
            last_accepted = run.last_accepted_simulated_at
            advanced = replace(
                run,
                last_accepted_simulated_at=(
                    context.simulated_at
                    if last_accepted is None or context.simulated_at > last_accepted
                    else last_accepted
                ),
                updated_at=datetime.now(UTC),
            )
            self.runs.save(advanced, commit=False)
            self.session.commit()
            simulation_operations_total.labels(operation, "accepted").inc()
            self._log(context, operation, result)
            return result
        except HTTPException:
            self.session.rollback()
            raise
        except Exception:
            self.session.rollback()
            simulation_operations_total.labels(operation, "technical_failure").inc()
            raise
        finally:
            simulation_transaction_duration_seconds.labels(operation).observe(
                perf_counter() - started
            )

    @staticmethod
    def _log(
        context: SimulationRequestContext,
        operation: str,
        result: SimulationMutationResult,
    ) -> None:
        logger.info(
            "simulated mutation completed",
            extra={
                "simulation_run_id": str(context.simulation_run_id),
                "simulation_event_id": str(context.simulation_event_id),
                "evdriver_id": str(context.evdriver_id),
                "operation": operation,
                "simulated_at": context.simulated_at.isoformat(),
                "idempotent_replay": result.replayed,
                "outcome": "accepted",
                "http_status": result.response_status,
            },
        )


def canonical_request_digest(
    *, operation: str, content: dict[str, Any], context: SimulationRequestContext
) -> str:
    canonical = {
        "operation": operation,
        "content": content,
        "simulated_at": context.simulated_at.isoformat(),
        "evdriver_id": str(context.evdriver_id),
        "simulation_run_id": str(context.simulation_run_id),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()


def _error(status_code: int, code: str, message: str) -> HTTPException:
    simulation_rejections_total.labels(code).inc()
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
