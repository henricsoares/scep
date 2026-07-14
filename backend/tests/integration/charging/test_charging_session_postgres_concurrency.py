import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from app.modules.charging.application.charging_session_service import (
    ChargingSessionConflictError,
    ChargingSessionService,
)
from app.modules.charging.application.reservation_service import ReservationService
from app.modules.charging.domain.facility import Facility, FacilityType
from app.modules.charging.domain.reservation import Reservation
from app.modules.charging.domain.station import ChargingStation, ConnectorStatus, ConnectorType
from app.modules.charging.domain.vehicle import Vehicle
from app.modules.charging.infrastructure.charging_session_repository import (
    SqlAlchemyChargingSessionRepository,
)
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.reservation_repository import (
    SqlAlchemyReservationRepository,
    SqlAlchemyVehicleRepository,
)
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from app.modules.identity.application.security import hash_password
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="POSTGRES_TEST_DATABASE_URL is required for race-safety tests"
)


def test_concurrent_activation_and_completion_are_serialized() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    now = datetime.now(UTC)

    with sessions() as session:
        actor = SqlAlchemyUserRepository(session).add(
            User.create(
                email=f"session-race-{now.timestamp()}@example.com",
                display_name="Session Race",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.EV_DRIVER],
                facility_ids=[],
            )
        )
        facility = SqlAlchemyFacilityRepository(session).add(
            Facility.create(
                name=f"Session Race {now.timestamp()}",
                facility_type=FacilityType.UNIVERSITY,
                timezone="UTC",
                country="Brazil",
                city="Juiz de Fora",
                address="Campus",
            )
        )
        station = SqlAlchemyChargingStationRepository(session).add(
            ChargingStation.create(
                facility_id=facility.id,
                name="Race Station",
                description=None,
                serial_number=f"SESSION-RACE-{now.timestamp()}",
                manufacturer=None,
                model=None,
                maximum_power_kw=22,
                connectors=[(ConnectorType.TYPE2, 22, ConnectorStatus.AVAILABLE)],
            )
        )
        vehicle = SqlAlchemyVehicleRepository(session).add(
            Vehicle.create(owner_id=actor.id, display_name="Race EV", now=now)
        )
        reservation = SqlAlchemyReservationRepository(session).add(
            Reservation.create(
                owner_id=actor.id,
                vehicle_id=vehicle.id,
                connector_id=station.connectors[0].id,
                start_at=now + timedelta(minutes=1),
                end_at=now + timedelta(hours=1),
                now=now,
            )
        )

    class FixedClock:
        def now(self) -> datetime:
            return now

    def service(session: Session) -> ChargingSessionService:
        return ChargingSessionService(
            SqlAlchemyChargingSessionRepository(session),
            ReservationService(
                SqlAlchemyReservationRepository(session),
                SqlAlchemyVehicleRepository(session),
                SqlAlchemyChargingStationRepository(session),
                SqlAlchemyFacilityRepository(session),
                FixedClock(),
            ),
            SqlAlchemyVehicleRepository(session),
            SqlAlchemyChargingStationRepository(session),
            FixedClock(),
        )

    def activate() -> tuple[str, str | None]:
        with sessions() as session:
            try:
                item = service(session).activate(reservation.id, actor=actor)
                return "OK", str(item.id)
            except ChargingSessionConflictError as exc:
                return exc.code, None

    with ThreadPoolExecutor(max_workers=2) as pool:
        activation_results = list(pool.map(lambda _index: activate(), range(2)))
    assert sorted(result[0] for result in activation_results) == [
        "OK",
        "RESERVATION_SESSION_CONFLICT",
    ]
    session_id = next(result[1] for result in activation_results if result[1] is not None)
    assert session_id is not None

    def complete() -> str:
        from uuid import UUID

        with sessions() as session:
            try:
                service(session).complete(UUID(session_id), actor=actor)
                return "OK"
            except ValueError:
                return "TERMINAL"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _index: complete(), range(2))) == ["OK", "TERMINAL"]
