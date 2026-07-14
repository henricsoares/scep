from datetime import UTC, datetime, timedelta

from app.infrastructure.database import Base
from app.modules.charging.application.charging_session_service import ChargingSessionService
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
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


class MutableClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


def test_completion_during_next_reservation_early_start_restores_reserved() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    event_time = datetime(2026, 7, 14, 12, tzinfo=UTC)
    creation_time = event_time - timedelta(hours=2)

    with sessions() as session:
        actor = SqlAlchemyUserRepository(session).add(
            User.create(
                email="early-start-restoration@example.com",
                display_name="Early Start Driver",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.EV_DRIVER],
                facility_ids=[],
            )
        )
        facility = SqlAlchemyFacilityRepository(session).add(
            Facility.create(
                name="Early Start Facility",
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
                name="Early Start Station",
                description=None,
                serial_number="EARLY-START-RESTORATION",
                manufacturer=None,
                model=None,
                maximum_power_kw=22,
                connectors=[(ConnectorType.TYPE2, 22, ConnectorStatus.AVAILABLE)],
            )
        )
        vehicles = [
            SqlAlchemyVehicleRepository(session).add(
                Vehicle.create(owner_id=actor.id, display_name=name, now=creation_time)
            )
            for name in ("Vehicle A", "Vehicle B")
        ]
        connector_id = station.connectors[0].id
        reservation_a = SqlAlchemyReservationRepository(session).add(
            Reservation.create(
                owner_id=actor.id,
                vehicle_id=vehicles[0].id,
                connector_id=connector_id,
                start_at=event_time - timedelta(minutes=30),
                end_at=event_time + timedelta(minutes=10),
                now=creation_time,
            )
        )
        reservation_b = SqlAlchemyReservationRepository(session).add(
            Reservation.create(
                owner_id=actor.id,
                vehicle_id=vehicles[1].id,
                connector_id=connector_id,
                start_at=event_time + timedelta(minutes=10),
                end_at=event_time + timedelta(hours=1),
                now=creation_time,
            )
        )

        clock = MutableClock(reservation_a.start_at)
        reservation_service = ReservationService(
            SqlAlchemyReservationRepository(session),
            SqlAlchemyVehicleRepository(session),
            SqlAlchemyChargingStationRepository(session),
            SqlAlchemyFacilityRepository(session),
            clock,
        )
        service = ChargingSessionService(
            SqlAlchemyChargingSessionRepository(session),
            reservation_service,
            SqlAlchemyVehicleRepository(session),
            SqlAlchemyChargingStationRepository(session),
            clock,
        )

        session_a = service.activate(reservation_a.id, actor=actor)
        clock.current = event_time
        service.complete(session_a.id, actor=actor)

        connector = SqlAlchemyChargingStationRepository(session).get_connector(connector_id)
        assert connector is not None
        assert connector.status == ConnectorStatus.RESERVED

        session_b = service.activate(reservation_b.id, actor=actor)
        assert session_b.reservation_id == reservation_b.id
        connector = SqlAlchemyChargingStationRepository(session).get_connector(connector_id)
        assert connector is not None
        assert connector.status == ConnectorStatus.CHARGING

    Base.metadata.drop_all(engine)
