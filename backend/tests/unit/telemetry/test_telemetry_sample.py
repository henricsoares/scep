from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from app.modules.telemetry.domain import TelemetrySample, TelemetrySource


def create_sample(**changes: object) -> TelemetrySample:
    values = {
        "session_id": uuid4(),
        "sample_id": "sample-1",
        "source": TelemetrySource.SIMULATOR,
        "recorded_at": datetime(2026, 7, 15, tzinfo=UTC),
        "received_at": datetime(2026, 7, 15, tzinfo=UTC),
        "power_kw": 7.2,
    }
    return TelemetrySample.create(**(values | changes))  # type: ignore[arg-type]


def test_create_valid_immutable_sample() -> None:
    sample = create_sample(power_kw=0, energy_kwh=0, state_of_charge_percent=100)
    assert sample.power_kw == 0
    with pytest.raises(FrozenInstanceError):
        sample.power_kw = 10  # type: ignore[misc]


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"power_kw": None}, "at least one"),
        ({"power_kw": -1}, "non-negative"),
        ({"power_kw": float("inf")}, "finite"),
        ({"power_kw": None, "energy_kwh": -1}, "non-negative"),
        ({"power_kw": None, "state_of_charge_percent": 101}, "between"),
        ({"sample_id": " "}, "sample_id"),
    ],
)
def test_rejects_invalid_observations(changes: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        create_sample(**changes)


def test_idempotency_ignores_platform_fields() -> None:
    first = create_sample()
    retry = TelemetrySample.create(
        session_id=first.session_id,
        sample_id=first.sample_id,
        source=first.source,
        recorded_at=first.recorded_at,
        received_at=datetime(2026, 7, 15, 1, tzinfo=UTC),
        power_kw=first.power_kw,
    )
    assert first.same_producer_payload(retry)
    assert not first.same_producer_payload(create_sample(power_kw=8.0))
