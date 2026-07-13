import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.modules.charging.application.reservation_metrics import reservations_no_show_total
from app.modules.charging.application.reservation_service import (
    ReservationService,
    SchedulingConflictError,
)
from app.modules.charging.domain.facility import Facility, FacilityType
from app.modules.charging.domain.reservation import Reservation, ReservationStatus
from app.modules.charging.domain.station import ChargingStation, ConnectorStatus, ConnectorType
from app.modules.charging.domain.vehicle import Vehicle
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.persistence_errors import (
    ReservationCalendarWriteConflict,
)
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
from sqlalchemy.orm import Session, sessionmaker

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

    class FixedClock:
        def now(self) -> datetime:
            return now

    def service(session: Session) -> ReservationService:
        return ReservationService(
            SqlAlchemyReservationRepository(session),
            SqlAlchemyVehicleRepository(session),
            SqlAlchemyChargingStationRepository(session),
            SqlAlchemyFacilityRepository(session),
            FixedClock(),
        )

    def create_through_service(vehicle: Vehicle) -> str:
        with sessions() as session:
            try:
                service(session).create(
                    actor=user,
                    vehicle_id=vehicle.id,
                    connector_id=station.connectors[0].id,
                    start_at=start + timedelta(hours=12),
                    end_at=start + timedelta(hours=13),
                )
                return "OK"
            except SchedulingConflictError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create_through_service, vehicles)) == [
            "CONNECTOR_RESERVATION_CONFLICT",
            "OK",
        ]

    def persist(item: Reservation) -> str:
        with sessions() as session:
            try:
                SqlAlchemyReservationRepository(session).add(item)
                return "OK"
            except ReservationCalendarWriteConflict as exc:
                assert exc.code is not None
                return exc.code

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
        assert sorted(pool.map(persist, connector_race)) == [
            "CONNECTOR_RESERVATION_CONFLICT",
            "OK",
        ]

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
        assert sorted(pool.map(persist, vehicle_race)) == [
            "OK",
            "VEHICLE_RESERVATION_CONFLICT",
        ]

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
    assert all(persist(item) == "OK" for item in reschedule_sources)
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

    def update(item: Reservation) -> str:
        with sessions() as session:
            try:
                SqlAlchemyReservationRepository(session).update(item)
                return "OK"
            except ReservationCalendarWriteConflict as exc:
                assert exc.code is not None
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(update, reschedule_targets)) == [
            "CONNECTOR_RESERVATION_CONFLICT",
            "OK",
        ]

    overdue = [
        replace(
            Reservation.create(
                owner_id=user.id,
                vehicle_id=vehicle.id,
                connector_id=connector.id,
                start_at=now + timedelta(hours=20),
                end_at=now + timedelta(hours=21),
                now=now,
            ),
            start_at=now - timedelta(hours=4 - number),
            end_at=now - timedelta(hours=3 - number),
        )
        for number, (vehicle, connector) in enumerate(
            zip(vehicles, station.connectors, strict=True)
        )
    ]
    active_control = replace(
        Reservation.create(
            owner_id=user.id,
            vehicle_id=vehicles[0].id,
            connector_id=station.connectors[0].id,
            start_at=now + timedelta(hours=20),
            end_at=now + timedelta(hours=21),
            now=now,
        ),
        start_at=now - timedelta(hours=1),
        end_at=now + timedelta(hours=1),
        status=ReservationStatus.ACTIVE,
        activated_at=now - timedelta(hours=1),
    )
    cancelled_control = replace(
        Reservation.create(
            owner_id=user.id,
            vehicle_id=vehicles[0].id,
            connector_id=station.connectors[0].id,
            start_at=now + timedelta(hours=20),
            end_at=now + timedelta(hours=21),
            now=now,
        ),
        start_at=now - timedelta(hours=2),
        end_at=now - timedelta(hours=1),
        status=ReservationStatus.CANCELLED,
        cancelled_at=now - timedelta(hours=3),
    )
    assert all(persist(item) == "OK" for item in [*overdue, active_control, cancelled_control])

    def reconcile() -> int:
        with sessions() as session:
            return service(session).reconcile_overdue()

    def no_show_metric_value() -> float:
        return next(
            sample.value
            for metric in reservations_no_show_total.collect()
            for sample in metric.samples
            if sample.name == "scep_reservations_no_show_total"
        )

    metric_before = no_show_metric_value()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _number: reconcile(), range(2))) == [0, 2]
    assert no_show_metric_value() - metric_before == 2
    assert reconcile() == 0
    assert no_show_metric_value() - metric_before == 2

    with sessions() as session:
        reconciled_models = [session.get(ReservationModel, item.id) for item in overdue]
        active_model = session.get(ReservationModel, active_control.id)
        cancelled_model = session.get(ReservationModel, cancelled_control.id)
        assert all(model is not None for model in reconciled_models)
        assert all(
            model.status == ReservationStatus.NO_SHOW.value
            for model in reconciled_models
            if model is not None
        )
        assert active_model is not None
        assert active_model.status == ReservationStatus.ACTIVE.value
        assert cancelled_model is not None
        assert cancelled_model.status == ReservationStatus.CANCELLED.value

    with sessions() as session:
        session.execute(delete(ReservationModel).where(ReservationModel.owner_id == user.id))
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
