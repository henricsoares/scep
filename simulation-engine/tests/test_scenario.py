from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.execution import Checkpoint
from app.scenarios.planner import ConnectorCandidate, DriverInventory, build_plan
from app.scenarios.schema import Scenario


def scenario(driver_id: UUID, facility_id: UUID) -> Scenario:
    start = datetime(2026, 1, 5, tzinfo=UTC)
    return Scenario.model_validate(
        {
            "scenario_id": "reference-week",
            "scenario_version": "1",
            "random_seed": 42,
            "logical_start_at": start,
            "logical_end_at": start + timedelta(days=7),
            "drivers": [
                {
                    "driver_id": driver_id,
                    "sessions_per_week": {"min": 2, "max": 2},
                    "weekday_weights": {"0": 1, "2": 1},
                    "hour_weights": {"9": 1, "18": 2},
                    "facility_weights": {str(facility_id): 1},
                    "reservation_probability": 1,
                    "cancellation_probability": 0,
                    "no_show_probability": 0,
                    "telemetry": {"enabled": True, "batch_size": 10},
                }
            ],
        }
    )


def test_plan_is_deterministic_chronological_and_uses_stable_event_ids() -> None:
    driver_id, facility_id, station_id, vehicle_id, connector_id = (
        uuid4() for _ in range(5)
    )
    configured = scenario(driver_id, facility_id)
    inventory = DriverInventory(
        driver_id=driver_id,
        vehicle_ids=[vehicle_id],
        connectors=[
            ConnectorCandidate(
                id=connector_id,
                facility_id=facility_id,
                station_id=station_id,
                connector_type="Type2",
                maximum_power_kw=22,
            )
        ],
    )
    first = build_plan(configured, {driver_id: inventory})
    second = build_plan(configured, {driver_id: inventory})
    assert first == second
    assert [item.simulated_at for item in first] == sorted(
        item.simulated_at for item in first
    )
    assert len({item.event_id for item in first}) == len(first)
    assert {item.operation for item in first} >= {
        "RESERVATION_CREATE",
        "SESSION_ACTIVATE",
        "SESSION_COMPLETE",
        "TELEMETRY_BATCH_CREATE",
    }


def test_scenario_rejects_invalid_probabilities_and_weights() -> None:
    driver_id, facility_id = uuid4(), uuid4()
    content = scenario(driver_id, facility_id).model_dump()
    content["drivers"][0]["cancellation_probability"] = 0.8
    content["drivers"][0]["no_show_probability"] = 0.4
    with pytest.raises(ValueError, match="must not exceed one"):
        Scenario.model_validate(content)


def test_checkpoint_round_trip_and_compatibility(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    run_id, event_id, resource_id = uuid4(), uuid4(), uuid4()
    item = Checkpoint(
        run_id=run_id,
        scenario_sha256="a" * 64,
        completed_event_ids={event_id},
        resource_ids={event_id: resource_id},
    )
    item.save(path)
    assert Checkpoint.load_or_create(path, run_id, "a" * 64) == item
    with pytest.raises(ValueError, match="does not match"):
        Checkpoint.load_or_create(path, run_id, "b" * 64)
