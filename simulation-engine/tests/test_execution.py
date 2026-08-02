import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest

from app.clients.backend import BackendClient, DomainRejected, TerminalBackendError
from app.execution import Checkpoint, execute_plan
from app.scenarios.planner import (
    ConnectorCandidate,
    DriverInventory,
    Operation,
    PlannedEvent,
)
from app.scenarios.schema import FailureHandling, RangeInt


class FakeBackendClient(BackendClient):
    def __init__(
        self,
        outcomes: list[tuple[dict[str, object], int] | Exception],
        connectors: list[ConnectorCandidate] | None = None,
    ) -> None:
        self.outcomes = outcomes
        self.connectors = connectors or []
        self.executed: list[PlannedEvent] = []
        self.inventory_calls = 0

    async def execute(
        self, event: PlannedEvent, resource_ids: dict[UUID, UUID]
    ) -> tuple[dict[str, object], int]:
        del resource_ids
        self.executed.append(event)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def inventory(
        self, driver_id: UUID, facility_ids: list[UUID]
    ) -> DriverInventory:
        del facility_ids
        self.inventory_calls += 1
        return DriverInventory(
            driver_id=driver_id,
            vehicle_ids=[],
            connectors=self.connectors,
        )


def connector(
    *, facility_id: UUID | None = None, station_id: UUID | None = None
) -> ConnectorCandidate:
    return ConnectorCandidate(
        id=uuid4(),
        facility_id=facility_id or uuid4(),
        station_id=station_id or uuid4(),
        connector_type="Type2",
        maximum_power_kw=22,
    )


def reservation_event(
    selected: ConnectorCandidate,
    *,
    failure_handling: FailureHandling | None = None,
) -> PlannedEvent:
    start = datetime(2026, 1, 5, 10, tzinfo=UTC)
    return PlannedEvent(
        event_id=uuid4(),
        flow_id=uuid4(),
        driver_id=uuid4(),
        operation=Operation.RESERVATION_CREATE,
        simulated_at=start - timedelta(hours=1),
        payload={
            "vehicle_id": str(uuid4()),
            "connector_id": str(selected.id),
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
        },
        failure_handling=failure_handling,
        selected_connector=selected,
    )


async def test_terminal_backend_error_fails_execution(tmp_path: Path) -> None:
    selected = connector()
    event = reservation_event(selected)
    client = FakeBackendClient(
        [TerminalBackendError(401, "SIMULATION_RUN_CREDENTIAL_INVALID", {})]
    )
    checkpoint = Checkpoint(run_id=uuid4(), scenario_sha256="a" * 64)

    report = await execute_plan(
        client=client,
        events=[event],
        checkpoint=checkpoint,
        checkpoint_path=tmp_path / "checkpoint.json",
        scenario_id="terminal",
        scenario_version="1",
        logical_end_at=datetime(2026, 1, 6, tzinfo=UTC),
    )

    assert report.state == "FAILED"
    assert report.terminal_failure_count == 1
    assert report.domain_rejected_event_count == 0


async def test_empty_plan_finishes_without_backend_calls(tmp_path: Path) -> None:
    client = FakeBackendClient([])
    checkpoint = Checkpoint(run_id=uuid4(), scenario_sha256="0" * 64)

    report = await execute_plan(
        client=client,
        events=[],
        checkpoint=checkpoint,
        checkpoint_path=tmp_path / "checkpoint.json",
        scenario_id="empty",
        scenario_version="1",
    )

    assert report.state == "FINISHED"
    assert report.planned_event_count == 0
    assert client.executed == []


async def test_resume_does_not_reexecute_resolved_rejection(tmp_path: Path) -> None:
    event = reservation_event(connector())
    client = FakeBackendClient([])
    checkpoint = Checkpoint(
        run_id=uuid4(),
        scenario_sha256="b" * 64,
        rejected_event_ids={event.event_id},
        resolved_event_ids={event.event_id},
        abandoned_flow_ids={event.flow_id},
    )

    report = await execute_plan(
        client=client,
        events=[event],
        checkpoint=checkpoint,
        checkpoint_path=tmp_path / "checkpoint.json",
        scenario_id="resume",
        scenario_version="1",
    )

    assert report.state == "FINISHED"
    assert client.executed == []
    assert report.domain_rejected_event_count == 1
    assert report.abandoned_flow_count == 1


async def test_expected_rejection_uses_refreshed_connector_and_new_event_id(
    tmp_path: Path,
) -> None:
    facility_id, station_id = uuid4(), uuid4()
    selected = connector(facility_id=facility_id, station_id=station_id)
    alternative = connector(facility_id=facility_id, station_id=station_id)
    policy = FailureHandling(
        maximum_alternative_attempts=1,
        maximum_rescheduling_attempts=0,
    )
    event = reservation_event(selected, failure_handling=policy)
    reservation_id = uuid4()
    client = FakeBackendClient(
        [
            DomainRejected(409, "CONNECTOR_RESERVATION_CONFLICT", {}),
            ({"reservation": {"id": str(reservation_id)}}, 0),
        ],
        [alternative],
    )
    checkpoint = Checkpoint(run_id=uuid4(), scenario_sha256="c" * 64)

    report = await execute_plan(
        client=client,
        events=[event],
        checkpoint=checkpoint,
        checkpoint_path=tmp_path / "checkpoint.json",
        scenario_id="alternative",
        scenario_version="1",
        authorized_facility_ids=[facility_id],
        logical_end_at=datetime(2026, 1, 6, tzinfo=UTC),
    )

    assert report.state == "FINISHED"
    assert client.inventory_calls == 1
    assert len(client.executed) == 2
    attempted = client.executed[1]
    assert attempted.event_id != event.event_id
    assert attempted.payload["connector_id"] == str(alternative.id)
    assert checkpoint.resource_ids[event.event_id] == reservation_id
    assert event.event_id in checkpoint.resolved_event_ids
    assert attempted.event_id in checkpoint.completed_event_ids


async def test_resume_retries_only_uncertain_fallback_with_same_event_id(
    tmp_path: Path,
) -> None:
    facility_id, station_id = uuid4(), uuid4()
    selected = connector(facility_id=facility_id, station_id=station_id)
    alternative = connector(facility_id=facility_id, station_id=station_id)
    event = reservation_event(
        selected,
        failure_handling=FailureHandling(
            maximum_alternative_attempts=1,
            maximum_rescheduling_attempts=0,
        ),
    )
    checkpoint_path = tmp_path / "checkpoint.json"
    checkpoint = Checkpoint(run_id=uuid4(), scenario_sha256="e" * 64)
    interrupted = FakeBackendClient(
        [
            DomainRejected(409, "CONNECTOR_RESERVATION_CONFLICT", {}),
            RuntimeError("response outcome is uncertain"),
        ],
        [alternative],
    )

    failed = await execute_plan(
        client=interrupted,
        events=[event],
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
        scenario_id="resume-fallback",
        scenario_version="1",
        authorized_facility_ids=[facility_id],
        logical_end_at=datetime(2026, 1, 6, tzinfo=UTC),
    )
    fallback_id = interrupted.executed[1].event_id
    assert failed.state == "FAILED"
    assert event.event_id in checkpoint.rejected_event_ids
    assert event.event_id not in checkpoint.resolved_event_ids

    resumed_checkpoint = Checkpoint.load_or_create(
        checkpoint_path, checkpoint.run_id, checkpoint.scenario_sha256
    )
    resumed = FakeBackendClient(
        [({"reservation": {"id": str(uuid4())}}, 0)],
    )
    finished = await execute_plan(
        client=resumed,
        events=[event],
        checkpoint=resumed_checkpoint,
        checkpoint_path=checkpoint_path,
        scenario_id="resume-fallback",
        scenario_version="1",
        authorized_facility_ids=[facility_id],
        logical_end_at=datetime(2026, 1, 6, tzinfo=UTC),
    )

    assert finished.state == "FINISHED"
    assert resumed.inventory_calls == 0
    assert [item.event_id for item in resumed.executed] == [fallback_id]
    assert event.event_id in resumed_checkpoint.resolved_event_ids


async def test_rescheduling_shifts_flow_and_uses_new_event_ids(tmp_path: Path) -> None:
    selected = connector()
    policy = FailureHandling(
        maximum_alternative_attempts=0,
        maximum_rescheduling_attempts=1,
        rescheduling_delay_minutes=RangeInt(min=15, max=15),
    )
    create = reservation_event(selected, failure_handling=policy)
    activate = PlannedEvent(
        event_id=uuid4(),
        flow_id=create.flow_id,
        driver_id=create.driver_id,
        operation=Operation.SESSION_ACTIVATE,
        simulated_at=datetime(2026, 1, 5, 10, tzinfo=UTC),
        payload={},
        depends_on=create.event_id,
    )
    reservation_id, session_id = uuid4(), uuid4()
    client = FakeBackendClient(
        [
            DomainRejected(409, "CONNECTOR_RESERVATION_CONFLICT", {}),
            ({"reservation": {"id": str(reservation_id)}}, 0),
            ({"id": str(session_id)}, 0),
        ],
        [selected],
    )
    checkpoint = Checkpoint(run_id=uuid4(), scenario_sha256="d" * 64)

    report = await execute_plan(
        client=client,
        events=[create, activate],
        checkpoint=checkpoint,
        checkpoint_path=tmp_path / "checkpoint.json",
        scenario_id="reschedule",
        scenario_version="1",
        authorized_facility_ids=[selected.facility_id],
        logical_end_at=datetime(2026, 1, 6, tzinfo=UTC),
    )

    assert report.state == "FINISHED"
    rescheduled, shifted_activation = client.executed[1:]
    assert rescheduled.event_id != create.event_id
    assert rescheduled.payload["start_at"] == "2026-01-05T10:15:00+00:00"
    assert shifted_activation.event_id != activate.event_id
    assert shifted_activation.simulated_at == datetime(2026, 1, 5, 10, 15, tzinfo=UTC)
    assert checkpoint.flow_time_shifts_minutes[create.flow_id] == 15


async def test_same_timestamp_barrier_preserves_causal_operation_order(
    tmp_path: Path,
) -> None:
    create = reservation_event(connector())
    cancel = PlannedEvent(
        event_id=uuid4(),
        flow_id=create.flow_id,
        driver_id=create.driver_id,
        operation=Operation.RESERVATION_CANCEL,
        simulated_at=create.simulated_at,
        payload={},
        depends_on=create.event_id,
    )
    reservation_id = uuid4()
    response: dict[str, object] = {"reservation": {"id": str(reservation_id)}}
    client = FakeBackendClient([(response, 0), (response, 0)])
    checkpoint = Checkpoint(run_id=uuid4(), scenario_sha256="f" * 64)

    report = await execute_plan(
        client=client,
        events=[cancel, create],
        checkpoint=checkpoint,
        checkpoint_path=tmp_path / "checkpoint.json",
        scenario_id="barrier-order",
        scenario_version="1",
        logical_end_at=datetime(2026, 1, 6, tzinfo=UTC),
    )

    assert report.state == "FINISHED"
    assert [item.operation for item in client.executed] == [
        Operation.RESERVATION_CREATE,
        Operation.RESERVATION_CANCEL,
    ]


async def test_retry_uses_same_event_id_and_bounded_jitter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = connector()
    event = reservation_event(selected)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503, json={"detail": "unavailable"})
        return httpx.Response(201, json={"reservation": {"id": str(uuid4())}})

    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("app.clients.backend.asyncio.sleep", fake_sleep)
    client = BackendClient(
        "http://backend",
        uuid4(),
        "run-token",
        {event.driver_id: "driver-token"},
        max_attempts=2,
        retry_random=random.Random(7),
    )
    await client.http.aclose()
    client.http = httpx.AsyncClient(
        base_url="http://backend", transport=httpx.MockTransport(handler)
    )
    try:
        _, retries = await client.execute(event, {})
    finally:
        await client.close()

    assert retries == 1
    assert len(requests) == 2
    assert requests[0].headers["X-Simulation-Event-Id"] == str(event.event_id)
    assert requests[1].headers["X-Simulation-Event-Id"] == str(event.event_id)
    assert len(sleeps) == 1
    assert 0 < sleeps[0] < 0.25


@pytest.mark.parametrize(
    ("status_code", "code"),
    [
        (401, "SIMULATION_RUN_CREDENTIAL_INVALID"),
        (403, "SIMULATION_FACILITY_NOT_AUTHORIZED"),
        (409, "SIMULATION_TIME_REGRESSION"),
        (409, "SIMULATION_EVENT_IDEMPOTENCY_CONFLICT"),
        (422, "SIMULATION_TIME_OUTSIDE_WINDOW"),
    ],
)
async def test_simulation_contract_errors_are_terminal(
    status_code: int, code: str
) -> None:
    selected = connector()
    event = reservation_event(selected)

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={
                "detail": {
                    "code": code,
                    "message": "terminal contract error",
                }
            },
        )

    client = BackendClient(
        "http://backend",
        uuid4(),
        "run-token",
        {event.driver_id: "driver-token"},
    )
    await client.http.aclose()
    client.http = httpx.AsyncClient(
        base_url="http://backend", transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(TerminalBackendError, match=f"HTTP {status_code}"):
            await client.execute(event, {})
    finally:
        await client.close()


@pytest.mark.parametrize(
    ("status_code", "code"),
    [
        (409, "CONNECTOR_RESERVATION_CONFLICT"),
        (422, None),
    ],
)
async def test_operational_rejections_remain_behavioral(
    status_code: int, code: str | None
) -> None:
    selected = connector()
    event = reservation_event(selected)
    detail: object = "connector is inactive"
    if code is not None:
        detail = {"code": code, "message": "capacity conflict"}

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"detail": detail})

    client = BackendClient(
        "http://backend",
        uuid4(),
        "run-token",
        {event.driver_id: "driver-token"},
    )
    await client.http.aclose()
    client.http = httpx.AsyncClient(
        base_url="http://backend", transport=httpx.MockTransport(handler)
    )
    try:
        with pytest.raises(DomainRejected):
            await client.execute(event, {})
    finally:
        await client.close()
