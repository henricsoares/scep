from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

from pydantic import BaseModel, Field, model_validator

from app.clients.backend import (
    BackendClient,
    DomainRejected,
    TerminalBackendError,
    parse_time,
    response_resource,
)
from app.scenarios.planner import (
    EVENT_NAMESPACE,
    ConnectorCandidate,
    Operation,
    PlannedEvent,
    operation_order,
)
from app.scenarios.schema import FailureHandling

logger = logging.getLogger(__name__)
SIMULATOR_VERSION = "1.0.0"


class Checkpoint(BaseModel):
    run_id: UUID
    scenario_sha256: str
    simulator_version: str = SIMULATOR_VERSION
    last_completed_timestamp_barrier: datetime | None = None
    completed_event_ids: set[UUID] = Field(default_factory=set)
    rejected_event_ids: set[UUID] = Field(default_factory=set)
    resolved_event_ids: set[UUID] = Field(default_factory=set)
    resource_ids: dict[UUID, UUID] = Field(default_factory=dict)
    generated_events: dict[UUID, PlannedEvent] = Field(default_factory=dict)
    fallback_event_ids: dict[UUID, list[UUID]] = Field(default_factory=dict)
    executed_events: dict[UUID, PlannedEvent] = Field(default_factory=dict)
    flow_time_shifts_minutes: dict[UUID, int] = Field(default_factory=dict)
    abandoned_flow_ids: set[UUID] = Field(default_factory=set)
    technical_retry_count: int = 0

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_resolved_events(cls, data: Any) -> Any:
        if isinstance(data, dict) and "resolved_event_ids" not in data:
            data = dict(data)
            data["resolved_event_ids"] = set(data.get("completed_event_ids", [])) | set(
                data.get("rejected_event_ids", [])
            )
        return data

    @model_validator(mode="after")
    def include_completed_events(self) -> "Checkpoint":
        self.resolved_event_ids.update(self.completed_event_ids)
        return self

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
    authorized_facility_ids: list[UUID] | None = None,
    logical_end_at: datetime | None = None,
) -> ExecutionReport:
    started = datetime.now(UTC)
    counters = Counters()
    facility_ids = authorized_facility_ids or sorted(
        {
            item.selected_connector.facility_id
            for item in events
            if item.selected_connector is not None
        },
        key=str,
    )
    window_end = logical_end_at or (
        max(item.simulated_at for item in events)
        if events
        else datetime.max.replace(tzinfo=UTC)
    )
    while True:
        pending = [
            item
            for item in events
            if item.event_id not in checkpoint.resolved_event_ids
        ]
        if not pending:
            break
        effective = [_shifted_event(item, checkpoint) for item in pending]
        simulated_at = min(item.simulated_at for item in effective)
        barrier = sorted(
            (item for item in effective if item.simulated_at == simulated_at),
            key=lambda item: (
                str(item.driver_id),
                operation_order(item.operation),
                str(item.event_id),
            ),
        )
        for event in barrier:
            source_event_id = _source_event_id(event)
            dependency = event.depends_on
            if (
                dependency is not None
                and dependency in checkpoint.resolved_event_ids
                and dependency not in checkpoint.resource_ids
            ):
                checkpoint.rejected_event_ids.add(event.event_id)
                checkpoint.resolved_event_ids.add(source_event_id)
                checkpoint.abandoned_flow_ids.add(event.flow_id)
                counters.rejected += 1
                counters.warnings.append(
                    f"dependency rejected for event {event.event_id}"
                )
                continue
            if event.event_id in checkpoint.rejected_event_ids:
                try:
                    recovered = await _recover_expected_rejection(
                        client=client,
                        event=event,
                        source_event_id=source_event_id,
                        checkpoint=checkpoint,
                        checkpoint_path=checkpoint_path,
                        facility_ids=facility_ids,
                        logical_end_at=window_end,
                        counters=counters,
                    )
                except Exception as recovery_error:
                    return _recovery_failure_report(
                        checkpoint=checkpoint,
                        checkpoint_path=checkpoint_path,
                        events=events,
                        counters=counters,
                        started=started,
                        scenario_id=scenario_id,
                        scenario_version=scenario_version,
                        event=event,
                        error=recovery_error,
                    )
                if not recovered:
                    checkpoint.resolved_event_ids.add(source_event_id)
                    checkpoint.abandoned_flow_ids.add(event.flow_id)
                continue
            try:
                body, retries = await client.execute(event, checkpoint.resource_ids)
                checkpoint.technical_retry_count += retries
                _record_success(checkpoint, source_event_id, event, body)
                counters.success += 1
                _log(event, "SUCCESS", 200, None)
            except DomainRejected as exc:
                checkpoint.rejected_event_ids.add(event.event_id)
                counters.rejected += 1
                _log(event, "DOMAIN_REJECTED", exc.status_code, exc.code)
                try:
                    recovered = await _recover_expected_rejection(
                        client=client,
                        event=event,
                        source_event_id=source_event_id,
                        checkpoint=checkpoint,
                        checkpoint_path=checkpoint_path,
                        facility_ids=facility_ids,
                        logical_end_at=window_end,
                        counters=counters,
                    )
                except Exception as recovery_error:
                    return _recovery_failure_report(
                        checkpoint=checkpoint,
                        checkpoint_path=checkpoint_path,
                        events=events,
                        counters=counters,
                        started=started,
                        scenario_id=scenario_id,
                        scenario_version=scenario_version,
                        event=event,
                        error=recovery_error,
                    )
                if not recovered:
                    checkpoint.resolved_event_ids.add(source_event_id)
                    checkpoint.abandoned_flow_ids.add(event.flow_id)
            except TerminalBackendError as exc:
                counters.terminal += 1
                counters.warnings.append(
                    f"event {event.event_id}: terminal backend error {exc.code or exc.status_code}"
                )
                _log(event, "TERMINAL_FAILURE", exc.status_code, exc.code)
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


def _recovery_failure_report(
    *,
    checkpoint: Checkpoint,
    checkpoint_path: Path,
    events: list[PlannedEvent],
    counters: Counters,
    started: datetime,
    scenario_id: str,
    scenario_version: str,
    event: PlannedEvent,
    error: Exception,
) -> ExecutionReport:
    counters.terminal += 1
    status = error.status_code if isinstance(error, TerminalBackendError) else None
    code = (
        error.code if isinstance(error, TerminalBackendError) else type(error).__name__
    )
    counters.warnings.append(f"event {event.event_id}: recovery failed: {error}")
    _log(event, "TERMINAL_FAILURE", status, code)
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


def _source_event_id(event: PlannedEvent) -> UUID:
    return event.source_event_id or event.event_id


def _shifted_event(event: PlannedEvent, checkpoint: Checkpoint) -> PlannedEvent:
    shift_minutes = checkpoint.flow_time_shifts_minutes.get(event.flow_id, 0)
    if shift_minutes == 0 or event.operation == Operation.RESERVATION_CREATE:
        return event
    shift = timedelta(minutes=shift_minutes)
    payload = dict(event.payload)
    if event.operation == Operation.TELEMETRY_BATCH_CREATE:
        raw_samples = payload.get("samples")
        if not isinstance(raw_samples, list):
            raise ValueError("telemetry event samples must be a list")
        payload["samples"] = [
            dict(sample)
            | {
                "recorded_at": (
                    parse_time(str(sample["recorded_at"])) + shift
                ).isoformat()
            }
            for sample in raw_samples
            if isinstance(sample, dict)
        ]
    shifted_id = uuid5(
        EVENT_NAMESPACE,
        f"{event.event_id}:FLOW_SHIFT:{shift_minutes}",
    )
    return event.model_copy(
        update={
            "event_id": shifted_id,
            "source_event_id": event.event_id,
            "simulated_at": event.simulated_at + shift,
            "payload": payload,
            "reschedule_shift_minutes": shift_minutes,
        }
    )


def _record_success(
    checkpoint: Checkpoint,
    source_event_id: UUID,
    event: PlannedEvent,
    body: dict[str, object] | list[object],
) -> None:
    resource_id = response_resource(event.operation, body)
    if resource_id is not None:
        checkpoint.resource_ids[event.event_id] = resource_id
        checkpoint.resource_ids[source_event_id] = resource_id
    checkpoint.completed_event_ids.add(event.event_id)
    checkpoint.resolved_event_ids.add(source_event_id)
    checkpoint.executed_events[event.event_id] = event
    if event.reschedule_shift_minutes:
        checkpoint.flow_time_shifts_minutes[event.flow_id] = (
            event.reschedule_shift_minutes
        )


async def _recover_expected_rejection(
    *,
    client: BackendClient,
    event: PlannedEvent,
    source_event_id: UUID,
    checkpoint: Checkpoint,
    checkpoint_path: Path,
    facility_ids: list[UUID],
    logical_end_at: datetime,
    counters: Counters,
) -> bool:
    policy = event.failure_handling
    if event.operation != Operation.RESERVATION_CREATE or policy is None:
        return False
    fallback_ids = checkpoint.fallback_event_ids.get(source_event_id)
    if fallback_ids is None:
        inventory = await client.inventory(event.driver_id, facility_ids)
        fallback_events = _fallback_events(event, inventory.connectors, logical_end_at)
        fallback_ids = [item.event_id for item in fallback_events]
        checkpoint.fallback_event_ids[source_event_id] = fallback_ids
        checkpoint.generated_events.update(
            {item.event_id: item for item in fallback_events}
        )
        checkpoint.save(checkpoint_path)
    for fallback_id in fallback_ids:
        fallback = checkpoint.generated_events[fallback_id]
        if fallback_id in checkpoint.completed_event_ids:
            resource_id = checkpoint.resource_ids.get(fallback_id)
            if resource_id is not None:
                checkpoint.resource_ids[source_event_id] = resource_id
            checkpoint.resolved_event_ids.add(source_event_id)
            if fallback.reschedule_shift_minutes:
                checkpoint.flow_time_shifts_minutes[event.flow_id] = (
                    fallback.reschedule_shift_minutes
                )
            return True
        if fallback_id in checkpoint.rejected_event_ids:
            continue
        checkpoint.save(checkpoint_path)
        try:
            body, retries = await client.execute(fallback, checkpoint.resource_ids)
        except DomainRejected as exc:
            checkpoint.rejected_event_ids.add(fallback_id)
            counters.rejected += 1
            _log(fallback, "DOMAIN_REJECTED", exc.status_code, exc.code)
            checkpoint.save(checkpoint_path)
            continue
        checkpoint.technical_retry_count += retries
        _record_success(checkpoint, source_event_id, fallback, body)
        counters.success += 1
        _log(fallback, "SUCCESS", 200, None)
        checkpoint.save(checkpoint_path)
        return True
    return False


def _fallback_events(
    event: PlannedEvent,
    refreshed: list[ConnectorCandidate],
    logical_end_at: datetime,
) -> list[PlannedEvent]:
    policy = event.failure_handling
    selected = event.selected_connector
    if policy is None or selected is None:
        return []
    compatible = [
        item
        for item in refreshed
        if item.id != selected.id
        and (
            not event.preferred_connector_types
            or item.connector_type in event.preferred_connector_types
        )
    ]
    alternatives = [
        item
        for item in sorted(compatible, key=lambda item: str(item.id))
        if (policy.try_another_connector and item.station_id == selected.station_id)
        or (
            policy.try_another_station
            and item.facility_id == selected.facility_id
            and item.station_id != selected.station_id
        )
        or (policy.try_another_facility and item.facility_id != selected.facility_id)
    ][: policy.maximum_alternative_attempts]
    generated = [
        _alternative_event(event, candidate, attempt)
        for attempt, candidate in enumerate(alternatives, start=1)
    ]
    cumulative_delay = 0
    for attempt in range(1, policy.maximum_rescheduling_attempts + 1):
        cumulative_delay += _rescheduling_delay(event.event_id, attempt, policy)
        rescheduled = _rescheduled_event(event, attempt, cumulative_delay)
        if parse_time(str(rescheduled.payload["end_at"])) > logical_end_at:
            break
        generated.append(rescheduled)
    return generated


def _alternative_event(
    event: PlannedEvent, candidate: ConnectorCandidate, attempt: int
) -> PlannedEvent:
    event_id = uuid5(
        EVENT_NAMESPACE,
        f"{event.event_id}:ALTERNATIVE:{attempt}:{candidate.id}",
    )
    return event.model_copy(
        update={
            "event_id": event_id,
            "source_event_id": _source_event_id(event),
            "attempt": attempt,
            "payload": dict(event.payload) | {"connector_id": str(candidate.id)},
            "selected_connector": candidate,
        }
    )


def _rescheduled_event(
    event: PlannedEvent, attempt: int, shift_minutes: int
) -> PlannedEvent:
    shift = timedelta(minutes=shift_minutes)
    start_at = parse_time(str(event.payload["start_at"])) + shift
    end_at = parse_time(str(event.payload["end_at"])) + shift
    event_id = uuid5(
        EVENT_NAMESPACE,
        f"{event.event_id}:RESCHEDULE:{attempt}:{shift_minutes}",
    )
    return event.model_copy(
        update={
            "event_id": event_id,
            "source_event_id": _source_event_id(event),
            "attempt": attempt,
            "payload": dict(event.payload)
            | {"start_at": start_at.isoformat(), "end_at": end_at.isoformat()},
            "reschedule_shift_minutes": shift_minutes,
        }
    )


def _rescheduling_delay(event_id: UUID, attempt: int, policy: FailureHandling) -> int:
    minimum = policy.rescheduling_delay_minutes.min
    maximum = policy.rescheduling_delay_minutes.max
    width = maximum - minimum + 1
    digest = hashlib.sha256(f"{event_id}:{attempt}".encode()).digest()
    return minimum + int.from_bytes(digest[:4], "big") % width


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
    completed = list(checkpoint.executed_events.values())
    if not completed:
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
        planned_event_count=len(events) + len(checkpoint.generated_events),
        successful_event_count=len(checkpoint.completed_event_ids),
        domain_rejected_event_count=len(checkpoint.rejected_event_ids),
        technical_retry_count=checkpoint.technical_retry_count,
        abandoned_flow_count=len(checkpoint.abandoned_flow_ids),
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
            _telemetry_sample_count(item)
            for item in completed
            if item.operation == Operation.TELEMETRY_BATCH_CREATE
        ),
        unresolved_warnings=counters.warnings,
    )


def _operation_count(events: list[PlannedEvent], operation: Operation) -> int:
    return sum(item.operation == operation for item in events)


def _telemetry_sample_count(event: PlannedEvent) -> int:
    samples = event.payload.get("samples")
    return len(samples) if isinstance(samples, list) else 0


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
