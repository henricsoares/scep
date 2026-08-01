from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from uuid import UUID

from app.clients.backend import BackendClient, fetch_backend_health
from app.core.config import Settings
from app.execution import Checkpoint, execute_plan, write_report
from app.scenarios.planner import DriverInventory, build_plan
from app.scenarios.schema import Bootstrap, Scenario

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def run() -> None:
    settings = Settings()
    await fetch_backend_health(
        settings.backend_url,
        max_attempts=settings.backend_health_retries,
        retry_delay_seconds=settings.backend_health_retry_delay_seconds,
    )
    if settings.scenario_path is None:
        logger.info("backend is healthy; no scenario configured")
        return
    if settings.bootstrap_path is None or settings.run_token is None:
        raise ValueError(
            "bootstrap path and run token are required when a scenario is configured"
        )
    if settings.driver_tokens_json is None:
        raise ValueError(
            "EVDriver bearer tokens are required when a scenario is configured"
        )
    scenario = Scenario.model_validate_json(Path(settings.scenario_path).read_text())
    bootstrap = Bootstrap.model_validate_json(Path(settings.bootstrap_path).read_text())
    digest = scenario.canonical_digest()
    if (
        settings.registered_scenario_sha256 is not None
        and settings.registered_scenario_sha256.lower() != digest
    ):
        raise ValueError(
            "scenario digest does not match the registered SimulationRun digest"
        )
    _validate_contract(scenario, bootstrap)
    driver_tokens = {
        UUID(driver_id): token
        for driver_id, token in json.loads(settings.driver_tokens_json).items()
    }
    client = BackendClient(
        settings.backend_url,
        bootstrap.simulation_run.id,
        settings.run_token,
        driver_tokens,
    )
    try:
        inventories: dict[UUID, DriverInventory] = {}
        for driver_id in bootstrap.authorized_evdriver_ids:
            inventories[driver_id] = await client.inventory(
                driver_id, bootstrap.authorized_facility_ids
            )
        plan = build_plan(scenario, inventories)
        checkpoint_path = Path(settings.checkpoint_path)
        checkpoint = Checkpoint.load_or_create(
            checkpoint_path, bootstrap.simulation_run.id, digest
        )
        report = await execute_plan(
            client=client,
            events=plan,
            checkpoint=checkpoint,
            checkpoint_path=checkpoint_path,
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.scenario_version,
        )
        write_report(report, Path(settings.report_path))
        logger.info(report.model_dump_json())
        if report.state != "FINISHED":
            raise RuntimeError("simulation execution failed; inspect report")
    finally:
        await client.close()


def _validate_contract(scenario: Scenario, bootstrap: Bootstrap) -> None:
    run = bootstrap.simulation_run
    if scenario.logical_start_at != run.logical_start_at:
        raise ValueError("scenario logical_start_at does not match bootstrap")
    if scenario.logical_end_at != run.logical_end_at:
        raise ValueError("scenario logical_end_at does not match bootstrap")
    configured_drivers = {item.driver_id for item in scenario.drivers}
    if not configured_drivers.issubset(set(bootstrap.authorized_evdriver_ids)):
        raise ValueError(
            "scenario contains an EVDriver outside bootstrap authorization"
        )
    authorized_facilities = set(bootstrap.authorized_facility_ids)
    for profile in scenario.drivers:
        if not set(profile.facility_weights).issubset(authorized_facilities):
            raise ValueError(
                "scenario Facility preference is outside bootstrap authorization"
            )


if __name__ == "__main__":
    asyncio.run(run())
