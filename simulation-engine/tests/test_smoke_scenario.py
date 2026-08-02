from argparse import Namespace
from datetime import UTC, datetime
from uuid import UUID

from app.scenarios.planner import (
    ConnectorCandidate,
    DriverInventory,
    Operation,
    build_plan,
)
from smoke.generate_scenario import build_smoke_scenario


def test_operator_smoke_scenario_produces_one_complete_flow() -> None:
    driver_id = UUID("00000000-0000-0000-0000-000000000001")
    vehicle_id = UUID("00000000-0000-0000-0000-000000000002")
    facility_id = UUID("00000000-0000-0000-0000-000000000003")
    station_id = UUID("00000000-0000-0000-0000-000000000004")
    connector_id = UUID("00000000-0000-0000-0000-000000000005")
    arguments = Namespace(
        logical_start_at=datetime(2026, 1, 5, tzinfo=UTC),
        logical_end_at=datetime(2026, 1, 6, tzinfo=UTC),
        session_hour=12,
        sessions_per_week=1,
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        facility_id=facility_id,
        station_id=station_id,
        connector_id=connector_id,
        connector_type="Type2",
        maximum_power_kw=22,
    )

    scenario = build_smoke_scenario(arguments)
    plan = build_plan(
        scenario,
        {
            driver_id: DriverInventory(
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
        },
    )

    assert [event.operation for event in plan] == [
        Operation.RESERVATION_CREATE,
        Operation.SESSION_ACTIVATE,
        Operation.TELEMETRY_BATCH_CREATE,
        Operation.SESSION_COMPLETE,
    ]
    assert plan[0].simulated_at == datetime(2026, 1, 5, 11, tzinfo=UTC)
    assert plan[-1].simulated_at == datetime(2026, 1, 5, 13, tzinfo=UTC)
    assert scenario.drivers[0].reservation_probability == 1
    assert scenario.drivers[0].cancellation_probability == 0
    assert scenario.drivers[0].no_show_probability == 0
    assert scenario.telemetry_defaults.enabled is True
