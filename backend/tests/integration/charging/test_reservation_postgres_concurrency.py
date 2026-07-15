import os
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

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
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.persistence_errors import (
    DEADLOCK_DETECTED,
    EXCLUSION_VIOLATION,
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
from sqlalchemy import Engine, create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL, reason="POSTGRES_TEST_DATABASE_URL is required for race-safety tests"
)


@dataclass(frozen=True)
class ReservationConcurrencyContext:
    engine: Engine
    sessions: sessionmaker[Session]
    now: datetime
    user: User
    facility: Facility
    station: ChargingStation
    vehicles: tuple[Vehicle, Vehicle]


@dataclass(frozen=True)
class RawWriteOutcome:
    reservation: Reservation
    result: str
    code: str | None = None
    sqlstate: str | None = None


@pytest.fixture
def reservation_context() -> Iterator[ReservationConcurrencyContext]:
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
        vehicles = tuple(
            SqlAlchemyVehicleRepository(session).add(
                Vehicle.create(owner_id=user.id, display_name=f"Vehicle {number}", now=now)
            )
            for number in (1, 2)
        )
        assert len(vehicles) == 2

    context = ReservationConcurrencyContext(
        engine=engine,
        sessions=sessions,
        now=now,
        user=user,
        facility=facility,
        station=station,
        vehicles=(vehicles[0], vehicles[1]),
    )
    try:
        yield context
    finally:
        with sessions() as session:
            session.rollback()
            session.execute(delete(ReservationModel).where(ReservationModel.owner_id == user.id))
            session.execute(delete(VehicleModel).where(VehicleModel.owner_id == user.id))
            session.execute(
                delete(ConnectorModel).where(ConnectorModel.charging_station_id == station.id)
            )
            session.execute(
                delete(ChargingStationModel).where(ChargingStationModel.id == station.id)
            )
            session.execute(delete(FacilityModel).where(FacilityModel.id == facility.id))
            session.execute(delete(UserModel).where(UserModel.id == user.id))
            session.commit()
        engine.dispose()


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


def service(context: ReservationConcurrencyContext, session: Session) -> ReservationService:
    return ReservationService(
        SqlAlchemyReservationRepository(session),
        SqlAlchemyVehicleRepository(session),
        SqlAlchemyChargingStationRepository(session),
        SqlAlchemyFacilityRepository(session),
        FixedClock(context.now),
    )


def create_through_service(
    context: ReservationConcurrencyContext,
    *,
    vehicle_id: UUID,
    connector_id: UUID,
    start_at: datetime,
    end_at: datetime,
) -> str:
    with context.sessions() as session:
        try:
            service(context, session).create(
                actor=context.user,
                vehicle_id=vehicle_id,
                connector_id=connector_id,
                start_at=start_at,
                end_at=end_at,
            )
            return "OK"
        except SchedulingConflictError as exc:
            return exc.code


def raw_add(context: ReservationConcurrencyContext, item: Reservation) -> RawWriteOutcome:
    with context.sessions() as session:
        try:
            SqlAlchemyReservationRepository(session).add(item)
            return RawWriteOutcome(item, "OK")
        except ReservationCalendarWriteConflict as exc:
            session.rollback()
            return RawWriteOutcome(item, "CONFLICT", exc.code, exc.sqlstate)


def raw_update(context: ReservationConcurrencyContext, item: Reservation) -> RawWriteOutcome:
    with context.sessions() as session:
        try:
            SqlAlchemyReservationRepository(session).update(item)
            return RawWriteOutcome(item, "OK")
        except ReservationCalendarWriteConflict as exc:
            session.rollback()
            return RawWriteOutcome(item, "CONFLICT", exc.code, exc.sqlstate)


def assert_raw_constraint_race(
    context: ReservationConcurrencyContext,
    items: list[Reservation],
    write: Callable[[ReservationConcurrencyContext, Reservation], RawWriteOutcome],
    expected_code: str,
) -> None:
    # Direct repository writes intentionally bypass the production advisory-lock path. PostgreSQL
    # may pick either a named exclusion violation or a deadlock victim for the losing transaction.
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda item: write(context, item), items))

    winners = [outcome for outcome in outcomes if outcome.result == "OK"]
    conflicts = [outcome for outcome in outcomes if outcome.result == "CONFLICT"]
    assert len(winners) == 1
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.sqlstate in {EXCLUSION_VIOLATION, DEADLOCK_DETECTED}

    if conflict.sqlstate == EXCLUSION_VIOLATION:
        assert conflict.code == expected_code
        return

    assert conflict.sqlstate == DEADLOCK_DETECTED
    assert conflict.code is None
    retry = write(context, conflict.reservation)
    assert retry.result == "CONFLICT"
    assert retry.sqlstate == EXCLUSION_VIOLATION
    assert retry.code == expected_code


def test_service_serializes_same_connector_creation(
    reservation_context: ReservationConcurrencyContext,
) -> None:
    context = reservation_context
    start = context.now + timedelta(hours=14)
    connector_id = context.station.connectors[0].id

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda vehicle: create_through_service(
                    context,
                    vehicle_id=vehicle.id,
                    connector_id=connector_id,
                    start_at=start,
                    end_at=start + timedelta(hours=1),
                ),
                context.vehicles,
            )
        )

    assert sorted(results) == ["CONNECTOR_RESERVATION_CONFLICT", "OK"]


def test_service_serializes_same_vehicle_creation(
    reservation_context: ReservationConcurrencyContext,
) -> None:
    context = reservation_context
    start = context.now + timedelta(hours=14)
    vehicle_id = context.vehicles[0].id

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda connector: create_through_service(
                    context,
                    vehicle_id=vehicle_id,
                    connector_id=connector.id,
                    start_at=start,
                    end_at=start + timedelta(hours=1),
                ),
                context.station.connectors,
            )
        )

    assert sorted(results) == ["OK", "VEHICLE_RESERVATION_CONFLICT"]


def test_service_serializes_concurrent_rescheduling(
    reservation_context: ReservationConcurrencyContext,
) -> None:
    context = reservation_context
    connector_id = context.station.connectors[0].id
    source_start = context.now + timedelta(hours=2)
    reservations = []
    for number, vehicle in enumerate(context.vehicles):
        with context.sessions() as session:
            item, _ = service(context, session).create(
                actor=context.user,
                vehicle_id=vehicle.id,
                connector_id=connector_id,
                start_at=source_start + timedelta(hours=2 * number),
                end_at=source_start + timedelta(hours=2 * number + 1),
            )
            reservations.append(item)

    target_start = context.now + timedelta(hours=10)

    def reschedule(item: Reservation) -> str:
        with context.sessions() as session:
            try:
                service(context, session).reschedule(
                    item.id,
                    actor=context.user,
                    vehicle_id=None,
                    start_at=target_start,
                    end_at=target_start + timedelta(hours=1),
                )
                return "OK"
            except SchedulingConflictError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reschedule, reservations))

    assert sorted(results) == ["CONNECTOR_RESERVATION_CONFLICT", "OK"]


def test_raw_connector_exclusion_constraint_accepts_postgres_race_outcomes(
    reservation_context: ReservationConcurrencyContext,
) -> None:
    context = reservation_context
    start = context.now + timedelta(hours=2)
    items = [
        Reservation.create(
            owner_id=context.user.id,
            vehicle_id=vehicle.id,
            connector_id=context.station.connectors[0].id,
            start_at=start,
            end_at=start + timedelta(hours=1),
            now=context.now,
        )
        for vehicle in context.vehicles
    ]
    assert_raw_constraint_race(context, items, raw_add, "CONNECTOR_RESERVATION_CONFLICT")


def test_raw_vehicle_exclusion_constraint_accepts_postgres_race_outcomes(
    reservation_context: ReservationConcurrencyContext,
) -> None:
    context = reservation_context
    start = context.now + timedelta(hours=2)
    items = [
        Reservation.create(
            owner_id=context.user.id,
            vehicle_id=context.vehicles[0].id,
            connector_id=connector.id,
            start_at=start,
            end_at=start + timedelta(hours=1),
            now=context.now,
        )
        for connector in context.station.connectors
    ]
    assert_raw_constraint_race(context, items, raw_add, "VEHICLE_RESERVATION_CONFLICT")


def test_raw_reschedule_constraint_accepts_postgres_race_outcomes(
    reservation_context: ReservationConcurrencyContext,
) -> None:
    context = reservation_context
    connector_id = context.station.connectors[0].id
    source_start = context.now + timedelta(hours=2)
    sources = [
        Reservation.create(
            owner_id=context.user.id,
            vehicle_id=vehicle.id,
            connector_id=connector_id,
            start_at=source_start + timedelta(hours=2 * number),
            end_at=source_start + timedelta(hours=2 * number + 1),
            now=context.now,
        )
        for number, vehicle in enumerate(context.vehicles, start=1)
    ]
    assert all(raw_add(context, item).result == "OK" for item in sources)
    target_start = context.now + timedelta(hours=10)
    targets = [
        item.reschedule(
            vehicle_id=item.vehicle_id,
            start_at=target_start,
            end_at=target_start + timedelta(hours=1),
            now=context.now,
        )
        for item in sources
    ]
    assert_raw_constraint_race(context, targets, raw_update, "CONNECTOR_RESERVATION_CONFLICT")


def test_overdue_reconciliation_is_concurrency_safe_and_idempotent(
    reservation_context: ReservationConcurrencyContext,
) -> None:
    context = reservation_context
    overdue = [
        replace(
            Reservation.create(
                owner_id=context.user.id,
                vehicle_id=vehicle.id,
                connector_id=connector.id,
                start_at=context.now + timedelta(hours=20),
                end_at=context.now + timedelta(hours=21),
                now=context.now,
            ),
            start_at=context.now - timedelta(hours=4 - number),
            end_at=context.now - timedelta(hours=3 - number),
        )
        for number, (vehicle, connector) in enumerate(
            zip(context.vehicles, context.station.connectors, strict=True)
        )
    ]
    active_control = replace(
        Reservation.create(
            owner_id=context.user.id,
            vehicle_id=context.vehicles[0].id,
            connector_id=context.station.connectors[0].id,
            start_at=context.now + timedelta(hours=20),
            end_at=context.now + timedelta(hours=21),
            now=context.now,
        ),
        start_at=context.now - timedelta(hours=1),
        end_at=context.now + timedelta(hours=1),
        status=ReservationStatus.ACTIVE,
        activated_at=context.now - timedelta(hours=1),
    )
    cancelled_control = replace(
        Reservation.create(
            owner_id=context.user.id,
            vehicle_id=context.vehicles[0].id,
            connector_id=context.station.connectors[0].id,
            start_at=context.now + timedelta(hours=20),
            end_at=context.now + timedelta(hours=21),
            now=context.now,
        ),
        start_at=context.now - timedelta(hours=2),
        end_at=context.now - timedelta(hours=1),
        status=ReservationStatus.CANCELLED,
        cancelled_at=context.now - timedelta(hours=3),
    )
    assert all(
        raw_add(context, item).result == "OK"
        for item in [*overdue, active_control, cancelled_control]
    )

    def reconcile() -> int:
        with context.sessions() as session:
            return service(context, session).reconcile_overdue()

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

    with context.sessions() as session:
        reconciled = [session.get(ReservationModel, item.id) for item in overdue]
        active = session.get(ReservationModel, active_control.id)
        cancelled = session.get(ReservationModel, cancelled_control.id)
        assert all(item is not None for item in reconciled)
        assert all(
            item.status == ReservationStatus.NO_SHOW.value
            for item in reconciled
            if item is not None
        )
        assert active is not None and active.status == ReservationStatus.ACTIVE.value
        assert cancelled is not None and cancelled.status == ReservationStatus.CANCELLED.value
