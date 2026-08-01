from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime, time, timedelta
from enum import StrEnum
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict

from app.scenarios.schema import DriverBehavior, Scenario, TelemetryConfig

EVENT_NAMESPACE = UUID("5f064fa5-a20d-43b3-a3a4-76f8dcb06413")


class Operation(StrEnum):
    RESERVATION_CREATE = "RESERVATION_CREATE"
    RESERVATION_CANCEL = "RESERVATION_CANCEL"
    SESSION_ACTIVATE = "SESSION_ACTIVATE"
    TELEMETRY_BATCH_CREATE = "TELEMETRY_BATCH_CREATE"
    SESSION_COMPLETE = "SESSION_COMPLETE"


class ConnectorCandidate(BaseModel):
    id: UUID
    facility_id: UUID
    connector_type: str
    maximum_power_kw: float


class DriverInventory(BaseModel):
    driver_id: UUID
    vehicle_ids: list[UUID]
    connectors: list[ConnectorCandidate]


class PlannedEvent(BaseModel):
    event_id: UUID
    flow_id: UUID
    driver_id: UUID
    operation: Operation
    simulated_at: datetime
    payload: dict[str, object]
    depends_on: UUID | None = None
    attempt: int = 0
    model_config = ConfigDict(frozen=True)


def build_plan(
    scenario: Scenario, inventories: dict[UUID, DriverInventory]
) -> list[PlannedEvent]:
    events: list[PlannedEvent] = []
    weeks = max(
        1, ((scenario.logical_end_at - scenario.logical_start_at).days + 6) // 7
    )
    for profile in sorted(scenario.drivers, key=lambda item: str(item.driver_id)):
        inventory = inventories.get(profile.driver_id)
        if inventory is None or not inventory.vehicle_ids or not inventory.connectors:
            continue
        rng = random.Random(_driver_seed(scenario.random_seed, profile.driver_id))
        for week in range(weeks):
            attempts = rng.randint(
                profile.sessions_per_week.min, profile.sessions_per_week.max
            )
            for number in range(attempts):
                flow_key = f"{scenario.scenario_id}:{profile.driver_id}:{week}:{number}"
                flow_id = uuid5(EVENT_NAMESPACE, flow_key)
                events.extend(
                    _flow_events(scenario, profile, inventory, rng, flow_id, week)
                )
    return sorted(
        events,
        key=lambda item: (
            item.simulated_at,
            str(item.driver_id),
            _operation_order(item.operation),
            str(item.event_id),
        ),
    )


def _flow_events(
    scenario: Scenario,
    profile: DriverBehavior,
    inventory: DriverInventory,
    rng: random.Random,
    flow_id: UUID,
    week: int,
) -> list[PlannedEvent]:
    if rng.random() > profile.reservation_probability:
        return []
    weekday = _weighted_choice(rng, profile.weekday_weights)
    hour = _weighted_choice(rng, profile.hour_weights)
    jitter = rng.randint(0, profile.start_time_jitter_minutes)
    first_day = scenario.logical_start_at + timedelta(days=week * 7)
    day_offset = (weekday - scenario.logical_start_at.weekday()) % 7
    selected_day = first_day + timedelta(days=day_offset)
    start = datetime.combine(
        selected_day.date(), time(hour=hour, minute=jitter), selected_day.tzinfo
    ).astimezone(UTC)
    duration = rng.randint(
        profile.session_duration_minutes.min, profile.session_duration_minutes.max
    )
    end = min(start + timedelta(minutes=duration), scenario.logical_end_at)
    lead = rng.randint(profile.lead_time_minutes.min, profile.lead_time_minutes.max)
    created_at = max(scenario.logical_start_at, start - timedelta(minutes=lead))
    if (
        start <= scenario.logical_start_at
        or start >= scenario.logical_end_at
        or end <= start
    ):
        return []
    connector = _connector(rng, profile, inventory.connectors)
    vehicle_id = inventory.vehicle_ids[rng.randrange(len(inventory.vehicle_ids))]
    create = _event(
        flow_id,
        profile.driver_id,
        Operation.RESERVATION_CREATE,
        created_at,
        {
            "vehicle_id": str(vehicle_id),
            "connector_id": str(connector.id),
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
        },
    )
    outcome = rng.random()
    if outcome < profile.cancellation_probability:
        cancel_at = min(
            start - timedelta(microseconds=1), created_at + timedelta(minutes=1)
        )
        return [
            create,
            _event(
                flow_id,
                profile.driver_id,
                Operation.RESERVATION_CANCEL,
                max(created_at, cancel_at),
                {},
                depends_on=create.event_id,
            ),
        ]
    if outcome < profile.cancellation_probability + profile.no_show_probability:
        return [create]
    activate = _event(
        flow_id,
        profile.driver_id,
        Operation.SESSION_ACTIVATE,
        start,
        {},
        depends_on=create.event_id,
    )
    events = [create, activate]
    telemetry = profile.telemetry or scenario.telemetry_defaults
    if telemetry.enabled:
        telemetry_at = max(start, end - timedelta(microseconds=1))
        utilization = rng.uniform(
            profile.power_utilization_factor.min,
            profile.power_utilization_factor.max,
        )
        events.append(
            _event(
                flow_id,
                profile.driver_id,
                Operation.TELEMETRY_BATCH_CREATE,
                telemetry_at,
                {
                    "samples": _telemetry_samples(
                        flow_id,
                        start,
                        telemetry_at,
                        connector.maximum_power_kw,
                        utilization,
                        telemetry,
                        rng,
                    )
                },
                depends_on=activate.event_id,
            )
        )
    events.append(
        _event(
            flow_id,
            profile.driver_id,
            Operation.SESSION_COMPLETE,
            end,
            {},
            depends_on=activate.event_id,
        )
    )
    return events


def _event(
    flow_id: UUID,
    driver_id: UUID,
    operation: Operation,
    simulated_at: datetime,
    payload: dict[str, object],
    *,
    depends_on: UUID | None = None,
) -> PlannedEvent:
    event_id = uuid5(EVENT_NAMESPACE, f"{flow_id}:{operation.value}:0")
    return PlannedEvent(
        event_id=event_id,
        flow_id=flow_id,
        driver_id=driver_id,
        operation=operation,
        simulated_at=simulated_at,
        payload=payload,
        depends_on=depends_on,
    )


def _weighted_choice(rng: random.Random, values: dict[int, float]) -> int:
    return rng.choices(list(values), weights=list(values.values()), k=1)[0]


def _connector(
    rng: random.Random, profile: DriverBehavior, candidates: list[ConnectorCandidate]
) -> ConnectorCandidate:
    eligible = [
        item
        for item in candidates
        if not profile.preferred_connector_types
        or item.connector_type in profile.preferred_connector_types
    ] or candidates
    eligible = sorted(eligible, key=lambda item: str(item.id))
    if profile.selection_strategy == "FIRST_ELIGIBLE":
        return eligible[0]
    weights = [profile.facility_weights.get(item.facility_id, 1.0) for item in eligible]
    return rng.choices(eligible, weights=weights, k=1)[0]


def _telemetry_samples(
    flow_id: UUID,
    start: datetime,
    end: datetime,
    maximum_power_kw: float,
    utilization: float,
    config: TelemetryConfig,
    rng: random.Random,
) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    recorded_at = start
    accumulated = 0.0
    while recorded_at <= end and len(samples) < min(1000, config.batch_size):
        noise = rng.uniform(-config.bounded_power_noise, config.bounded_power_noise)
        power = max(
            0.0,
            min(maximum_power_kw, maximum_power_kw * (utilization + noise)),
        )
        accumulated += power * config.sampling_interval_minutes / 60
        samples.append(
            {
                "sample_id": f"{flow_id}-{len(samples)}",
                "source": "SIMULATOR",
                "recorded_at": recorded_at.isoformat(),
                "power_kw": round(power, 6),
                "energy_kwh": round(accumulated, 6),
            }
        )
        recorded_at += timedelta(minutes=config.sampling_interval_minutes)
    return samples


def _driver_seed(seed: int, driver_id: UUID) -> int:
    digest = hashlib.sha256(f"{seed}:{driver_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _operation_order(operation: Operation) -> int:
    return {
        Operation.RESERVATION_CREATE: 0,
        Operation.RESERVATION_CANCEL: 1,
        Operation.SESSION_ACTIVATE: 2,
        Operation.TELEMETRY_BATCH_CREATE: 3,
        Operation.SESSION_COMPLETE: 4,
    }[operation]
