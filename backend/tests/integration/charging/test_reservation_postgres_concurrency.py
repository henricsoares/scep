import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from app.modules.charging.domain.facility import Facility, FacilityType
from app.modules.charging.domain.reservation import Reservation
from app.modules.charging.domain.station import ChargingStation, ConnectorStatus, ConnectorType
from app.modules.charging.domain.vehicle import Vehicle
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.reservation_model import ReservationModel, VehicleModel
from app.modules.charging.infrastructure.reservation_repository import (
    SqlAlchemyReservationRepository,
    SqlAlchemyVehicleRepository,
)
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from app.modules.identity.application.security import hash_password
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_model import UserModel
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from sqlalchemy import create_engine, delete
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="POSTGRES_TEST_DATABASE_URL is required for race-safety tests"
)


def test_postgres_exclusion_constraints_protect_connector_and_vehicle_calendars() -> None:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    now = datetime.now(UTC)

    with sessions() as session:
        user = SqlAlchemyUserRepository(session).add(
            User.create(
                email=f"concurrency-{now.timestamp()}@example.com",
                display_name="Concurrency Test",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.EV_DRIVER],
                facility_ids=[],
            )
        )
        facility = SqlAlchemyFacilityRepository(session).add(
            Facility.create(
                name=f"Concurrency Facility {now.timestamp()}",
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
                name="Concurrency Station",
                description=None,
                serial_number=f"CONCURRENCY-{now.timestamp()}",
                manufacturer=None,
                model=None,
                maximum_power_kw=44,
                connectors=[
                    (ConnectorType.TYPE2, 22, ConnectorStatus.AVAILABLE),
                    (ConnectorType.CCS2, 22, ConnectorStatus.AVAILABLE),
                ],
            )
        )
        vehicles = [
            SqlAlchemyVehicleRepository(session).add(
                Vehicle.create(owner_id=user.id, display_name=f"Vehicle {number}", now=now)
            )
            for number in (1, 2)
        ]

    start = now + timedelta(hours=2)

    def persist(item: Reservation) -> bool:
        with sessions() as session:
            try:
                SqlAlchemyReservationRepository(session).add(item)
                return True
            except DBAPIError:
                return False

    connector_race = [
        Reservation.create(
            owner_id=user.id,
            vehicle_id=vehicle.id,
            connector_id=station.connectors[0].id,
            start_at=start,
            end_at=start + timedelta(hours=1),
            now=now,
        )
        for vehicle in vehicles
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(persist, connector_race)) == [False, True]

    with sessions() as session:
        session.execute(
            delete(ReservationModel).where(
                ReservationModel.id.in_([item.id for item in connector_race])
            )
        )
        session.commit()

    vehicle_race = [
        Reservation.create(
            owner_id=user.id,
            vehicle_id=vehicles[0].id,
            connector_id=connector.id,
            start_at=start,
            end_at=start + timedelta(hours=1),
            now=now,
        )
        for connector in station.connectors
    ]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(persist, vehicle_race)) == [False, True]

    with sessions() as session:
        session.execute(
            delete(ReservationModel).where(
                ReservationModel.id.in_([item.id for item in vehicle_race])
            )
        )
        session.commit()

    reschedule_sources = [
        Reservation.create(
            owner_id=user.id,
            vehicle_id=vehicle.id,
            connector_id=station.connectors[0].id,
            start_at=start + timedelta(hours=2 * number),
            end_at=start + timedelta(hours=2 * number + 1),
            now=now,
        )
        for number, vehicle in enumerate(vehicles, start=1)
    ]
    assert all(persist(item) for item in reschedule_sources)
    target_start = start + timedelta(hours=8)
    reschedule_targets = [
        item.reschedule(
            vehicle_id=item.vehicle_id,
            start_at=target_start,
            end_at=target_start + timedelta(hours=1),
            now=now,
        )
        for item in reschedule_sources
    ]

    def update(item: Reservation) -> bool:
        with sessions() as session:
            try:
                SqlAlchemyReservationRepository(session).update(item)
                return True
            except DBAPIError:
                return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update, reschedule_targets)) == [False, True]

    with sessions() as session:
        session.execute(
            delete(ReservationModel).where(
                ReservationModel.id.in_([item.id for item in reschedule_sources])
            )
        )
        session.execute(delete(VehicleModel).where(VehicleModel.owner_id == user.id))
        session.execute(
            delete(ConnectorModel).where(ConnectorModel.charging_station_id == station.id)
        )
        session.execute(delete(ChargingStationModel).where(ChargingStationModel.id == station.id))
        from app.modules.charging.infrastructure.facility_model import FacilityModel

        session.execute(delete(FacilityModel).where(FacilityModel.id == facility.id))
        session.execute(delete(UserModel).where(UserModel.id == user.id))
        session.commit()
    engine.dispose()
