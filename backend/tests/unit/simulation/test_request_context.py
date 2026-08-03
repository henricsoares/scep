from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.simulation.context import SimulationRequestContext
from app.modules.simulation.coordinator import canonical_request_digest


def test_fixed_context_clock_and_canonical_digest_are_stable() -> None:
    context = SimulationRequestContext(
        simulation_run_id=uuid4(),
        simulation_event_id=uuid4(),
        simulated_at=datetime(2026, 1, 1, 12, tzinfo=UTC),
        evdriver_id=uuid4(),
    )
    first = canonical_request_digest(
        operation="RESERVATION_CREATE",
        content={"vehicle_id": "one", "interval": {"end": "two", "start": "one"}},
        context=context,
    )
    second = canonical_request_digest(
        operation="RESERVATION_CREATE",
        content={"interval": {"start": "one", "end": "two"}, "vehicle_id": "one"},
        context=context,
    )
    assert context.clock.now() == context.simulated_at
    assert first == second
    assert len(first) == 64
    changed = SimulationRequestContext(
        simulation_run_id=context.simulation_run_id,
        simulation_event_id=context.simulation_event_id,
        simulated_at=context.simulated_at + timedelta(seconds=1),
        evdriver_id=context.evdriver_id,
    )
    assert canonical_request_digest(
        operation="RESERVATION_CREATE", content={}, context=context
    ) != canonical_request_digest(operation="RESERVATION_CREATE", content={}, context=changed)
