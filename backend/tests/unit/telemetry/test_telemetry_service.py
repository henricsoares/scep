from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from app.modules.charging.domain.charging_session import ChargingSessionStatus
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.telemetry.domain import TelemetrySample, TelemetrySource
from app.modules.telemetry.service import TelemetryNotFoundError, TelemetryService


def user(*, roles: tuple[HumanRole, ...] = (), facilities: tuple[UUID, ...] = ()) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="actor@example.com",
        display_name="Actor",
        password_hash="hash",
        account_type=AccountType.HUMAN,
        status=AccountStatus.ACTIVE,
        roles=roles,
        facility_ids=facilities,
        created_at=now,
        updated_at=now,
    )


def sample(session_id: object, now: datetime) -> TelemetrySample:
    return TelemetrySample.create(
        session_id=session_id,  # type: ignore[arg-type]
        sample_id="one",
        source=TelemetrySource.API_CLIENT,
        recorded_at=now,
        received_at=now,
        power_kw=1,
    )


def test_active_clock_skew_and_completed_interval() -> None:
    now = datetime.now(UTC)
    TelemetryService._validate_time(now, None, ChargingSessionStatus.ACTIVE, sample(uuid4(), now))
    with pytest.raises(ValueError):
        future = sample(uuid4(), now).create(
            session_id=uuid4(),
            sample_id="future",
            source=TelemetrySource.API_CLIENT,
            recorded_at=now.replace(year=now.year + 1),
            received_at=now,
            power_kw=1,
        )
        TelemetryService._validate_time(now, None, ChargingSessionStatus.ACTIVE, future)


def test_facility_operator_can_read_but_ingestion_is_concealed() -> None:
    now = datetime.now(UTC)
    facility_id = uuid4()
    session_id = uuid4()
    owner_id = uuid4()
    connector_id = uuid4()
    charging_session = SimpleNamespace(
        id=session_id,
        owner_id=owner_id,
        connector_id=connector_id,
        status=ChargingSessionStatus.ACTIVE,
        started_at=now,
        ended_at=None,
    )
    sessions = SimpleNamespace(
        get=lambda _id: charging_session,
        facility_id_for_connector=lambda _id: facility_id,
    )
    telemetry = SimpleNamespace(list=lambda *_args, **_kwargs: [], get=lambda _id: None)
    service = TelemetryService(telemetry, sessions)  # type: ignore[arg-type]
    operator = user(roles=(HumanRole.FACILITY_OPERATOR,), facilities=(facility_id,))

    assert service.list(session_id, actor=operator) == []
    with pytest.raises(TelemetryNotFoundError):
        service.ingest(session_id, [sample(session_id, now)], actor=operator, batch=False)
