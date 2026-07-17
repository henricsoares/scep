from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.charging.domain.charging_session import ChargingSession
from app.modules.charging.domain.reservation import Reservation
from app.modules.events.contracts import charging_session_event, reservation_event, telemetry_event
from app.modules.telemetry.domain import TelemetrySample, TelemetrySource


def test_all_seven_v1_contracts() -> None:
    now = datetime.now(UTC)
    reservation = Reservation.create(
        owner_id=uuid4(),
        vehicle_id=uuid4(),
        connector_id=uuid4(),
        start_at=now + timedelta(hours=2),
        end_at=now + timedelta(hours=3),
        now=now,
    )
    assert reservation_event("created", reservation).event_type == "reservation.created"
    assert reservation_event("rescheduled", reservation).event_type == "reservation.rescheduled"
    assert reservation_event("cancelled", reservation, cancellation_type="STANDARD").payload == {
        "cancellation_type": "STANDARD"
    }
    assert (
        reservation_event("marked-no-show", reservation).event_type == "reservation.marked-no-show"
    )
    session = ChargingSession.activate(
        reservation_id=reservation.id,
        owner_id=reservation.owner_id,
        vehicle_id=reservation.vehicle_id,
        connector_id=reservation.connector_id,
        now=now,
    )
    assert set(charging_session_event("started", session).payload) == {
        "reservation_id",
        "owner_id",
        "vehicle_id",
        "connector_id",
        "started_at",
    }
    completed = session.complete(now=now + timedelta(hours=1))
    assert set(charging_session_event("completed", completed).payload) == {
        "reservation_id",
        "ended_at",
    }
    sample = TelemetrySample.create(
        session_id=session.id,
        sample_id="one",
        source=TelemetrySource.API_CLIENT,
        recorded_at=now,
        received_at=now,
        power_kw=7.2,
    )
    assert set(telemetry_event(sample).payload) == {
        "session_id",
        "sample_id",
        "source",
        "recorded_at",
        "power_kw",
    }
