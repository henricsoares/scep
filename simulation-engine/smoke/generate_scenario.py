from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from uuid import UUID

from app.scenarios.planner import (
    ConnectorCandidate,
    DriverInventory,
    Operation,
    build_plan,
)
from app.scenarios.schema import Scenario


def parse_timestamp(value: str) -> datetime:
    item = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if item.tzinfo is None:
        raise argparse.ArgumentTypeError("timestamps require an explicit offset")
    return item


def positive_integer(value: str) -> int:
    item = int(value)
    if item < 1:
        raise argparse.ArgumentTypeError("value must be at least one")
    return item


def build_smoke_scenario(args: argparse.Namespace) -> Scenario:
    weekday = args.logical_start_at.weekday()
    scenario = Scenario.model_validate(
        {
            "schema_version": "1.0",
            "scenario_id": "spec-013-operator-smoke",
            "scenario_version": "1",
            "random_seed": 13013,
            "logical_start_at": args.logical_start_at,
            "logical_end_at": args.logical_end_at,
            "telemetry_defaults": {
                "enabled": True,
                "sampling_interval_minutes": 15,
                "batch_size": 100,
                "bounded_power_noise": 0,
            },
            "drivers": [
                {
                    "driver_id": args.driver_id,
                    "sessions_per_week": {
                        "min": args.sessions_per_week,
                        "max": args.sessions_per_week,
                    },
                    "weekday_weights": {weekday: 1},
                    "hour_weights": {args.session_hour: 1},
                    "start_time_jitter_minutes": 0,
                    "facility_weights": {args.facility_id: 1},
                    "preferred_connector_types": [args.connector_type],
                    "selection_strategy": "FIRST_ELIGIBLE",
                    "reservation_probability": 1,
                    "cancellation_probability": 0,
                    "no_show_probability": 0,
                    "lead_time_minutes": {"min": 60, "max": 60},
                    "session_duration_minutes": {"min": 60, "max": 60},
                    "power_utilization_factor": {"min": 0.5, "max": 0.5},
                    "telemetry": {
                        "enabled": True,
                        "sampling_interval_minutes": 15,
                        "batch_size": 100,
                        "bounded_power_noise": 0,
                    },
                    "failure_handling": {
                        "try_another_connector": False,
                        "try_another_station": False,
                        "try_another_facility": False,
                        "maximum_alternative_attempts": 0,
                        "rescheduling_delay_minutes": {"min": 15, "max": 15},
                        "maximum_rescheduling_attempts": 0,
                    },
                }
            ],
        }
    )
    _validate_generated_plan(scenario, args)
    return scenario


def _validate_generated_plan(scenario: Scenario, args: argparse.Namespace) -> None:
    inventory = DriverInventory(
        driver_id=args.driver_id,
        vehicle_ids=[args.vehicle_id],
        connectors=[
            ConnectorCandidate(
                id=args.connector_id,
                facility_id=args.facility_id,
                station_id=args.station_id,
                connector_type=args.connector_type,
                maximum_power_kw=args.maximum_power_kw,
            )
        ],
    )
    plan = build_plan(scenario, {args.driver_id: inventory})
    expected = {
        Operation.RESERVATION_CREATE,
        Operation.SESSION_ACTIVATE,
        Operation.TELEMETRY_BATCH_CREATE,
        Operation.SESSION_COMPLETE,
    }
    operations = {event.operation for event in plan}
    if args.sessions_per_week == 1 and operations != expected:
        names = ", ".join(item.value for item in sorted(operations, key=str))
        raise ValueError(f"smoke window does not produce one complete flow: {names}")
    if not plan or any(event.simulated_at > scenario.logical_end_at for event in plan):
        raise ValueError("smoke plan is empty or exceeds the logical window")


def parser() -> argparse.ArgumentParser:
    item = argparse.ArgumentParser(description="Generate the SPEC-013 smoke scenario")
    item.add_argument("--output", required=True, type=Path)
    item.add_argument("--logical-start-at", required=True, type=parse_timestamp)
    item.add_argument("--logical-end-at", required=True, type=parse_timestamp)
    item.add_argument("--session-hour", required=True, type=int, choices=range(24))
    item.add_argument("--sessions-per-week", required=True, type=positive_integer)
    item.add_argument("--driver-id", required=True, type=UUID)
    item.add_argument("--vehicle-id", required=True, type=UUID)
    item.add_argument("--facility-id", required=True, type=UUID)
    item.add_argument("--station-id", required=True, type=UUID)
    item.add_argument("--connector-id", required=True, type=UUID)
    item.add_argument("--connector-type", required=True)
    item.add_argument("--maximum-power-kw", required=True, type=float)
    return item


def main() -> None:
    args = parser().parse_args()
    scenario = build_smoke_scenario(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(scenario.model_dump_json(indent=2) + "\n")
    args.output.chmod(0o600)
    plan = build_plan(
        scenario,
        {
            args.driver_id: DriverInventory(
                driver_id=args.driver_id,
                vehicle_ids=[args.vehicle_id],
                connectors=[
                    ConnectorCandidate(
                        id=args.connector_id,
                        facility_id=args.facility_id,
                        station_id=args.station_id,
                        connector_type=args.connector_type,
                        maximum_power_kw=args.maximum_power_kw,
                    )
                ],
            )
        },
    )
    print(
        f"validated {len(plan)} deterministic event(s) in the smoke plan",
        file=sys.stderr,
    )
    print(scenario.canonical_digest())


if __name__ == "__main__":
    main()
