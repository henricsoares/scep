from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from itertools import groupby
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field

from app.clients.backend import BackendClient, DomainRejected, response_resource
from app.scenarios.planner import Operation, PlannedEvent

logger = logging.getLogger(__name__)
SIMULATOR_VERSION = "1.0.0"


class Checkpoint(BaseModel):
    run_id: UUID
    scenario_sha256: str
    simulator_version: str = SIMULATOR_VERSION
    last_completed_timestamp_barrier: datetime | None = None
    completed_event_ids: set[UUID] = Field(default_factory=set)
    rejected_event_ids: set[UUID] = Field(default_factory=set)
    resource_ids: dict[UUID, UUID] = Field(default_factory=dict)
    technical_retry_count: int = 0

    @classmethod
    def load_or_create(
        cls, path: Path, run_id: UUID, scenario_sha256: str
    ) -> "Checkpoint":
        if not path.exists():
            return cls(run_id=run_id, scenario_sha256=scenario_sha256)
        item = cls.model_validate_json(path.read_text())
        if item.run_id != run_id or item.scenario_sha256 != scenario_sha256:
            raise ValueError("checkpoint run or scenario digest does not match")
        if item.simulator_version != SIMULATOR_VERSION:
            raise ValueError("checkpoint simulator version does not match")
        return item

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(self.model_dump_json(indent=2))
        temporary.replace(path)


class ExecutionReport(BaseModel):
    run_id: UUID
    scenario_id: str
    scenario_version: str
    scenario_sha256: str
    simulator_version: str = SIMULATOR_VERSION
    state: str
    real_started_at: datetime
    real_finished_at: datetime
    last_processed_logical_timestamp: datetime | None
    planned_event_count: int
    successful_event_count: int
    domain_rejected_event_count: int
    technical_retry_count: int
    abandoned_flow_count: int
    terminal_failure_count: int
    reservations_created: int
    reservations_cancelled: int
    charging_sessions_activated: int
    charging_sessions_completed: int
    telemetry_samples_submitted: int
    unresolved_warnings: list[str]


@dataclass
class Counters:
    success: int = 0
    rejected: int = 0
    terminal: int = 0
    reservations_created: int = 0
    reservations_cancelled: int = 0
    sessions_activated: int = 0
    sessions_completed: int = 0
    telemetry_samples: int = 0
    warnings: list[str] = field(default_factory=list)


async def execute_plan(
    *,
    client: BackendClient,
    events: list[PlannedEvent],
    checkpoint: Checkpoint,
    checkpoint_path: Path,
    scenario_id: str,
    scenario_version: str,
) -> ExecutionReport:
    started = datetime.now(UTC)
    counters = Counters()
    pending = [
        item for item in events if item.event_id not in checkpoint.completed_event_ids
    ]
    for simulated_at, barrier_iter in groupby(
        pending, key=lambda item: item.simulated_at
    ):
        barrier = list(barrier_iter)
        for event in barrier:
            if event.depends_on in checkpoint.rejected_event_ids:
                checkpoint.rejected_event_ids.add(event.event_id)
                counters.rejected += 1
                counters.warnings.append(
                    f"dependency rejected for event {event.event_id}"
                )
                continue
            try:
                body, retries = await client.execute(event, checkpoint.resource_ids)
                checkpoint.technical_retry_count += retries
                resource_id = response_resource(event.operation, body)
                if resource_id is not None:
                    checkpoint.resource_ids[event.event_id] = resource_id
                checkpoint.completed_event_ids.add(event.event_id)
                counters.success += 1
                _count_success(counters, event, body)
                _log(event, "SUCCESS", 200, None)
            except DomainRejected as exc:
                checkpoint.rejected_event_ids.add(event.event_id)
                counters.rejected += 1
                _log(event, "DOMAIN_REJECTED", exc.status_code, exc.code)
            except Exception as exc:
                counters.terminal += 1
                counters.warnings.append(f"event {event.event_id}: {exc}")
                _log(event, "TERMINAL_FAILURE", None, type(exc).__name__)
                checkpoint.save(checkpoint_path)
                return _report(
                    checkpoint,
                    events,
                    counters,
                    started,
                    scenario_id,
                    scenario_version,
                    "FAILED",
                )
        checkpoint.last_completed_timestamp_barrier = simulated_at
        checkpoint.save(checkpoint_path)
    return _report(
        checkpoint,
        events,
        counters,
        started,
        scenario_id,
        scenario_version,
        "FINISHED",
    )


def write_report(report: ExecutionReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2))


def _count_success(
    counters: Counters, event: PlannedEvent, body: dict[str, object] | list[object]
) -> None:
    if event.operation == Operation.RESERVATION_CREATE:
        counters.reservations_created += 1
    elif event.operation == Operation.RESERVATION_CANCEL:
        counters.reservations_cancelled += 1
    elif event.operation == Operation.SESSION_ACTIVATE:
        counters.sessions_activated += 1
    elif event.operation == Operation.SESSION_COMPLETE:
        counters.sessions_completed += 1
    elif event.operation == Operation.TELEMETRY_BATCH_CREATE and isinstance(body, list):
        counters.telemetry_samples += len(body)


def _report(
    checkpoint: Checkpoint,
    events: list[PlannedEvent],
    counters: Counters,
    started: datetime,
    scenario_id: str,
    scenario_version: str,
    state: str,
) -> ExecutionReport:
    rejected_flows = {
        item.flow_id
        for item in events
        if item.event_id in checkpoint.rejected_event_ids
    }
    completed = [
        item for item in events if item.event_id in checkpoint.completed_event_ids
    ]
    return ExecutionReport(
        run_id=checkpoint.run_id,
        scenario_id=scenario_id,
        scenario_version=scenario_version,
        scenario_sha256=checkpoint.scenario_sha256,
        state=state,
        real_started_at=started,
        real_finished_at=datetime.now(UTC),
        last_processed_logical_timestamp=checkpoint.last_completed_timestamp_barrier,
        planned_event_count=len(events),
        successful_event_count=len(checkpoint.completed_event_ids),
        domain_rejected_event_count=len(checkpoint.rejected_event_ids),
        technical_retry_count=checkpoint.technical_retry_count,
        abandoned_flow_count=len(rejected_flows),
        terminal_failure_count=counters.terminal,
        reservations_created=_operation_count(completed, Operation.RESERVATION_CREATE),
        reservations_cancelled=_operation_count(
            completed, Operation.RESERVATION_CANCEL
        ),
        charging_sessions_activated=_operation_count(
            completed, Operation.SESSION_ACTIVATE
        ),
        charging_sessions_completed=_operation_count(
            completed, Operation.SESSION_COMPLETE
        ),
        telemetry_samples_submitted=sum(
            len(item.payload.get("samples", []))
            for item in completed
            if item.operation == Operation.TELEMETRY_BATCH_CREATE
        ),
        unresolved_warnings=counters.warnings,
    )


def _operation_count(events: list[PlannedEvent], operation: Operation) -> int:
    return sum(item.operation == operation for item in events)


def _log(
    event: PlannedEvent, outcome: str, status: int | None, code: str | None
) -> None:
    logger.info(
        json.dumps(
            {
                "event": "simulation_event",
                "event_id": str(event.event_id),
                "driver_id": str(event.driver_id),
                "logical_time": event.simulated_at.isoformat(),
                "operation": event.operation.value,
                "attempt": event.attempt,
                "outcome": outcome,
                "http_status": status,
                "domain_error_code": code,
            }
        )
    )
