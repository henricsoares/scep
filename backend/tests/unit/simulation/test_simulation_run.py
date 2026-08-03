from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from app.modules.simulation.domain import SimulationRun, SimulationRunStatus
from app.modules.simulation.security import issue_run_credential, verify_run_credential


def now() -> datetime:
    return datetime(2026, 1, 1, tzinfo=UTC)


def draft() -> SimulationRun:
    current = now()
    return SimulationRun.create(
        logical_start_at=current,
        logical_end_at=current + timedelta(days=7),
        facility_ids=[uuid4()],
        evdriver_ids=[uuid4()],
        created_by=uuid4(),
        now=current,
        scenario_sha256="a" * 64,
    )


def test_simulation_run_lifecycle_is_irreversible() -> None:
    item = draft()
    assert item.status == SimulationRunStatus.DRAFT
    running = item.start(credential_hash="hash", now=now() + timedelta(seconds=1))
    completed = running.complete(now=now() + timedelta(seconds=2))
    assert completed.status == SimulationRunStatus.COMPLETED
    with pytest.raises(ValueError, match="only RUNNING"):
        completed.complete(now=now() + timedelta(seconds=3))
    with pytest.raises(ValueError, match="only DRAFT or RUNNING"):
        completed.cancel(now=now() + timedelta(seconds=3))


def test_start_requires_associations_and_cancel_invalidates_credential() -> None:
    item = draft().update_draft(now=now(), facility_ids=[])
    with pytest.raises(ValueError, match="at least one"):
        item.start(credential_hash="hash", now=now())
    cancelled = draft().start(credential_hash="hash", now=now()).cancel(now=now())
    assert cancelled.status == SimulationRunStatus.CANCELLED
    assert cancelled.credential_hash is None


def test_window_and_sha256_are_validated() -> None:
    with pytest.raises(ValueError, match="must precede"):
        SimulationRun.create(
            logical_start_at=now(),
            logical_end_at=now(),
            facility_ids=[],
            evdriver_ids=[],
            created_by=uuid4(),
            now=now(),
        )
    with pytest.raises(ValueError, match="scenario_sha256"):
        SimulationRun.create(
            logical_start_at=now(),
            logical_end_at=now() + timedelta(days=1),
            facility_ids=[],
            evdriver_ids=[],
            created_by=uuid4(),
            now=now(),
            scenario_sha256="not-a-digest",
        )


def test_run_credential_is_high_entropy_hashed_and_verifiable() -> None:
    plaintext, credential_hash = issue_run_credential()
    assert len(plaintext) >= 64
    assert plaintext not in credential_hash
    assert verify_run_credential(plaintext, credential_hash)
    assert not verify_run_credential("wrong-token", credential_hash)
