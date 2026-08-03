import os
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from app.modules.charging.domain.facility import Facility, FacilityType
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.charging.infrastructure.facility_repository import (
    SqlAlchemyFacilityRepository,
)
from app.modules.identity.application.security import hash_password
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_model import UserModel
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from app.modules.simulation.context import SimulationRequestContext
from app.modules.simulation.coordinator import (
    SimulationMutationCoordinator,
    SimulationMutationResult,
)
from app.modules.simulation.domain import SimulationRun
from app.modules.simulation.infrastructure import (
    SimulationEventReceiptModel,
    SimulationRunModel,
    SimulationRunRepository,
)
from app.modules.simulation.security import issue_run_credential
from app.modules.simulation.service import SimulationRunService
from app.shared.clock import FixedClock
from fastapi import HTTPException
from sqlalchemy import Engine, create_engine, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="POSTGRES_TEST_DATABASE_URL is required for simulation concurrency tests",
)


@dataclass(frozen=True)
class SimulationConcurrencyContext:
    engine: Engine
    sessions: sessionmaker[Session]
    user: User
    facility_id: UUID
    run_id: UUID
    logical_start: datetime


@pytest.fixture
def simulation_concurrency_context() -> Iterator[SimulationConcurrencyContext]:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    now = datetime.now(UTC)
    with sessions() as session:
        user = SqlAlchemyUserRepository(session).add(
            User.create(
                email=f"simulation-concurrency-{uuid4()}@example.com",
                display_name="Simulation Concurrency",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.EV_DRIVER],
                facility_ids=[],
            )
        )
        facility = SqlAlchemyFacilityRepository(session).add(
            Facility.create(
                name=f"Simulation Concurrency {uuid4()}",
                facility_type=FacilityType.UNIVERSITY,
                timezone="UTC",
                country="Brazil",
                city="Juiz de Fora",
                address="Synthetic Campus",
            )
        )
        _, credential_hash = issue_run_credential()
        draft = SimulationRun.create(
            logical_start_at=now,
            logical_end_at=now + timedelta(days=1),
            facility_ids=[facility.id],
            evdriver_ids=[user.id],
            created_by=user.id,
            now=now,
        )
        runs = SimulationRunRepository(session)
        runs.add(draft)
        run = runs.save(draft.start(credential_hash=credential_hash, now=now))
    context = SimulationConcurrencyContext(
        engine=engine,
        sessions=sessions,
        user=user,
        facility_id=facility.id,
        run_id=run.id,
        logical_start=now,
    )
    try:
        yield context
    finally:
        with sessions() as session:
            session.execute(
                delete(SimulationEventReceiptModel).where(
                    SimulationEventReceiptModel.simulation_run_id == run.id
                )
            )
            session.execute(delete(SimulationRunModel).where(SimulationRunModel.id == run.id))
            session.execute(delete(FacilityModel).where(FacilityModel.id == facility.id))
            session.execute(delete(UserModel).where(UserModel.id == user.id))
            session.commit()
        engine.dispose()


def mutation(
    context: SimulationConcurrencyContext,
    *,
    event_id: UUID,
    simulated_at: datetime,
    action: Callable[[], SimulationMutationResult],
    content: dict[str, str] | None = None,
) -> str:
    with context.sessions() as session:
        try:
            result = SimulationMutationCoordinator(session).execute(
                context=SimulationRequestContext(
                    simulation_run_id=context.run_id,
                    simulation_event_id=event_id,
                    simulated_at=simulated_at,
                    evdriver_id=context.user.id,
                ),
                operation="CONCURRENCY_TEST",
                canonical_content=content or {"value": "stable"},
                facility_id=context.facility_id,
                action=action,
            )
            return "REPLAY" if result.replayed else "ACCEPTED"
        except HTTPException as exc:
            detail = exc.detail
            assert isinstance(detail, dict)
            return str(detail["code"])


def result(resource_id: UUID | None = None) -> SimulationMutationResult:
    identifier = resource_id or uuid4()
    return SimulationMutationResult(
        response_status=201,
        response_snapshot={"id": str(identifier)},
        resource_type="ConcurrencyProbe",
        resource_id=identifier,
    )


def test_equal_timestamps_serialize_on_the_run_row(
    simulation_concurrency_context: SimulationConcurrencyContext,
) -> None:
    context = simulation_concurrency_context
    active = 0
    maximum_active = 0
    guard = threading.Lock()

    def action() -> SimulationMutationResult:
        nonlocal active, maximum_active
        with guard:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.05)
        with guard:
            active -= 1
        return result()

    simulated_at = context.logical_start + timedelta(hours=1)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(
            pool.map(
                lambda event_id: mutation(
                    context,
                    event_id=event_id,
                    simulated_at=simulated_at,
                    action=action,
                ),
                [uuid4(), uuid4()],
            )
        )

    assert outcomes == ["ACCEPTED", "ACCEPTED"]
    assert maximum_active == 1
    with context.sessions() as session:
        run = session.get(SimulationRunModel, context.run_id)
        assert run is not None
        assert run.last_accepted_simulated_at == simulated_at


def test_concurrent_duplicate_event_executes_domain_action_once(
    simulation_concurrency_context: SimulationConcurrencyContext,
) -> None:
    context = simulation_concurrency_context
    event_id = uuid4()
    action_calls = 0
    guard = threading.Lock()
    expected = result()

    def action() -> SimulationMutationResult:
        nonlocal action_calls
        with guard:
            action_calls += 1
        time.sleep(0.05)
        return expected

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                mutation,
                context,
                event_id=event_id,
                simulated_at=context.logical_start + timedelta(hours=2),
                action=action,
            )
            for _ in range(2)
        ]
        outcomes = [future.result() for future in futures]

    assert sorted(outcomes) == ["ACCEPTED", "REPLAY"]
    assert action_calls == 1
    with context.sessions() as session:
        count = session.scalar(
            select(func.count())
            .select_from(SimulationEventReceiptModel)
            .where(SimulationEventReceiptModel.simulation_run_id == context.run_id)
        )
        assert count == 1


def test_inverted_concurrent_timestamp_is_rejected_after_newer_commit(
    simulation_concurrency_context: SimulationConcurrencyContext,
) -> None:
    context = simulation_concurrency_context
    newer_has_lock = threading.Event()
    release_newer = threading.Event()

    def newer_action() -> SimulationMutationResult:
        newer_has_lock.set()
        assert release_newer.wait(timeout=5)
        return result()

    with ThreadPoolExecutor(max_workers=2) as pool:
        newer = pool.submit(
            mutation,
            context,
            event_id=uuid4(),
            simulated_at=context.logical_start + timedelta(hours=4),
            action=newer_action,
        )
        assert newer_has_lock.wait(timeout=5)
        older = pool.submit(
            mutation,
            context,
            event_id=uuid4(),
            simulated_at=context.logical_start + timedelta(hours=3),
            action=result,
        )
        time.sleep(0.05)
        release_newer.set()
        outcomes = [newer.result(), older.result()]

    assert outcomes == ["ACCEPTED", "SIMULATION_TIME_REGRESSION"]


def test_concurrent_divergent_duplicate_returns_idempotency_conflict(
    simulation_concurrency_context: SimulationConcurrencyContext,
) -> None:
    context = simulation_concurrency_context
    event_id = uuid4()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                mutation,
                context,
                event_id=event_id,
                simulated_at=context.logical_start + timedelta(hours=3),
                action=result,
                content={"value": value},
            )
            for value in ("first", "second")
        ]
        outcomes = [future.result() for future in futures]

    assert sorted(outcomes) == [
        "ACCEPTED",
        "SIMULATION_EVENT_IDEMPOTENCY_CONFLICT",
    ]


def test_completion_serializes_after_in_flight_mutation(
    simulation_concurrency_context: SimulationConcurrencyContext,
) -> None:
    context = simulation_concurrency_context
    mutation_has_lock = threading.Event()
    release_mutation = threading.Event()

    def action() -> SimulationMutationResult:
        mutation_has_lock.set()
        assert release_mutation.wait(timeout=5)
        return result()

    def complete() -> str:
        with context.sessions() as session:
            item = SimulationRunService(
                session,
                FixedClock(context.logical_start + timedelta(hours=5)),
            ).complete(context.run_id)
            return item.status.value

    with ThreadPoolExecutor(max_workers=2) as pool:
        mutating = pool.submit(
            mutation,
            context,
            event_id=uuid4(),
            simulated_at=context.logical_start + timedelta(hours=4),
            action=action,
        )
        assert mutation_has_lock.wait(timeout=5)
        completing = pool.submit(complete)
        time.sleep(0.05)
        release_mutation.set()
        assert mutating.result() == "ACCEPTED"
        assert completing.result() == "COMPLETED"

    assert (
        mutation(
            context,
            event_id=uuid4(),
            simulated_at=context.logical_start + timedelta(hours=5),
            action=result,
        )
        == "SIMULATION_RUN_NOT_RUNNING"
    )
