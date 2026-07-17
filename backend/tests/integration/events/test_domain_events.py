from __future__ import annotations

import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event as ThreadEvent
from uuid import uuid4

import pytest
from app.infrastructure.database import get_db
from app.main import create_app
from app.modules.charging.domain.facility import Facility, FacilityType
from app.modules.charging.domain.reservation import Reservation
from app.modules.charging.domain.station import ChargingStation, ConnectorStatus, ConnectorType
from app.modules.charging.domain.vehicle import Vehicle
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.reservation_model import ReservationModel
from app.modules.charging.infrastructure.reservation_repository import (
    SqlAlchemyVehicleRepository,
)
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from app.modules.events.contracts import reservation_event
from app.modules.events.dispatcher import InternalEventDispatcher
from app.modules.events.domain import DeliveryStatus, DomainEvent
from app.modules.events.infrastructure import (
    ConsumerRegistry,
    DomainEventModel,
    EventDeliveryModel,
    EventPublisher,
    registry,
)
from app.modules.identity.application.security import create_access_token, hash_password
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine, delete, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="POSTGRES_TEST_DATABASE_URL is required for Domain Event integration tests",
)


@pytest.fixture
def sessions() -> sessionmaker[Session]:
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def isolate_event_store(sessions: sessionmaker[Session]) -> None:
    with sessions() as session:
        session.execute(text("TRUNCATE TABLE event_deliveries, domain_events"))
        session.commit()


@pytest.fixture(autouse=True)
def disable_automatic_dispatch(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr("app.modules.events.infrastructure._post_commit_dispatch", None)


def make_reservation(sessions: sessionmaker[Session]) -> Reservation:
    now = datetime.now(UTC)
    suffix = uuid4().hex
    with sessions() as session:
        actor = SqlAlchemyUserRepository(session).add(
            User.create(
                email=f"events-{suffix}@example.com",
                display_name="Domain Events Test",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.EV_DRIVER],
                facility_ids=[],
            )
        )
        facility = SqlAlchemyFacilityRepository(session).add(
            Facility.create(
                name=f"Domain Events {suffix}",
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
                name="Event Station",
                description=None,
                serial_number=f"EVENT-{suffix}",
                manufacturer=None,
                model=None,
                maximum_power_kw=22,
                connectors=[(ConnectorType.TYPE2, 22, ConnectorStatus.AVAILABLE)],
            )
        )
        vehicle = SqlAlchemyVehicleRepository(session).add(
            Vehicle.create(owner_id=actor.id, display_name="Event EV", now=now)
        )
    return Reservation.create(
        owner_id=actor.id,
        vehicle_id=vehicle.id,
        connector_id=station.connectors[0].id,
        start_at=now + timedelta(hours=2),
        end_at=now + timedelta(hours=3),
        now=now,
    )


def model(item: Reservation) -> ReservationModel:
    return ReservationModel(**item.__dict__ | {"status": item.status.value})


def test_aggregate_event_and_delivery_commit_atomically(
    sessions: sessionmaker[Session],
) -> None:
    reservation = make_reservation(sessions)
    consumer = f"atomic-{uuid4()}"
    consumers = ConsumerRegistry()
    consumers.register(consumer, lambda _event: None, ["reservation.created"])

    with sessions() as session:
        session.add(model(reservation))
        event = reservation_event("created", reservation)
        EventPublisher(session, consumers).publish(event)
        session.commit()

    with sessions() as session:
        assert session.get(ReservationModel, reservation.id) is not None
        persisted = session.get(DomainEventModel, event.id)
        delivery = session.scalar(
            select(EventDeliveryModel).where(EventDeliveryModel.event_id == event.id)
        )
        assert persisted is not None
        assert delivery is not None
        assert delivery.consumer == consumer

    assert InternalEventDispatcher(sessions, consumers).recover() == 1


def test_rollback_persists_neither_aggregate_nor_event(
    sessions: sessionmaker[Session],
) -> None:
    reservation = make_reservation(sessions)
    event = reservation_event("created", reservation)
    with sessions() as session:
        session.add(model(reservation))
        EventPublisher(session, ConsumerRegistry()).publish(event)
        session.flush()
        session.rollback()

    with sessions() as session:
        assert session.get(ReservationModel, reservation.id) is None
        assert session.get(DomainEventModel, event.id) is None
        assert (
            session.scalar(
                select(EventDeliveryModel).where(EventDeliveryModel.event_id == event.id)
            )
            is None
        )


def test_dispatch_occurs_only_after_commit(
    sessions: sessionmaker[Session], monkeypatch: MonkeyPatch
) -> None:
    reservation = make_reservation(sessions)
    observed: list[bool] = []
    consumers = ConsumerRegistry()

    def consume(_event: DomainEvent) -> None:
        with sessions() as verification:
            observed.append(verification.get(ReservationModel, reservation.id) is not None)

    consumers.register(f"after-commit-{uuid4()}", consume, ["reservation.created"])
    dispatcher = InternalEventDispatcher(sessions, consumers)
    monkeypatch.setattr(
        "app.modules.events.infrastructure._post_commit_dispatch", dispatcher.recover
    )

    with sessions() as session:
        session.add(model(reservation))
        EventPublisher(session, consumers).publish(reservation_event("created", reservation))
        session.flush()
        assert observed == []
        session.commit()

    assert observed == [True]


def test_pending_failed_and_independent_consumers_are_recovered(
    sessions: sessionmaker[Session],
) -> None:
    attempts = {"successful": 0, "flaky": 0}
    allow_flaky_success = False
    consumers = ConsumerRegistry()

    def successful(_event: DomainEvent) -> None:
        attempts["successful"] += 1

    def flaky(_event: DomainEvent) -> None:
        attempts["flaky"] += 1
        if not allow_flaky_success:
            raise RuntimeError("temporary consumer failure")

    successful_name = f"successful-{uuid4()}"
    flaky_name = f"flaky-{uuid4()}"
    consumers.register(successful_name, successful)
    consumers.register(flaky_name, flaky)
    event = DomainEvent(
        event_type="reservation.created",
        aggregate_id=uuid4(),
        aggregate_type="Reservation",
        producer_module="charging",
        occurred_at=datetime.now(UTC),
        payload={"owner_id": str(uuid4())},
    )
    with sessions() as session:
        EventPublisher(session, consumers).publish(event)
        session.commit()

    dispatcher = InternalEventDispatcher(sessions, consumers)
    assert dispatcher.recover() == 2
    with sessions() as session:
        outcomes = {
            item.consumer: item
            for item in session.scalars(
                select(EventDeliveryModel).where(EventDeliveryModel.event_id == event.id)
            )
        }
        assert outcomes[successful_name].status == DeliveryStatus.DISPATCHED.value
        assert outcomes[successful_name].attempts == 1
        assert outcomes[flaky_name].status == DeliveryStatus.FAILED.value
        assert outcomes[flaky_name].attempts == 1
        assert outcomes[flaky_name].last_error == "temporary consumer failure"

    allow_flaky_success = True
    assert dispatcher.recover() == 1
    with sessions() as session:
        outcomes = {
            item.consumer: item
            for item in session.scalars(
                select(EventDeliveryModel).where(EventDeliveryModel.event_id == event.id)
            )
        }
        assert outcomes[successful_name].attempts == 1
        assert outcomes[flaky_name].status == DeliveryStatus.DISPATCHED.value
        assert outcomes[flaky_name].attempts == 2
        assert outcomes[flaky_name].last_error is None


def test_same_delivery_cannot_be_processed_concurrently(
    sessions: sessionmaker[Session],
) -> None:
    started = ThreadEvent()
    release = ThreadEvent()
    executions = 0
    consumers = ConsumerRegistry()

    def blocking(_event: DomainEvent) -> None:
        nonlocal executions
        executions += 1
        started.set()
        assert release.wait(timeout=5)

    consumer = f"blocking-{uuid4()}"
    consumers.register(consumer, blocking)
    event = DomainEvent(
        event_type="reservation.created",
        aggregate_id=uuid4(),
        aggregate_type="Reservation",
        producer_module="charging",
        occurred_at=datetime.now(UTC),
        payload={"owner_id": str(uuid4())},
    )
    with sessions() as session:
        EventPublisher(session, consumers).publish(event)
        session.commit()

    dispatcher = InternalEventDispatcher(sessions, consumers)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(dispatcher.dispatch_one)
        assert started.wait(timeout=5)
        second = pool.submit(dispatcher.dispatch_one)
        assert second.result(timeout=5) is None
        release.set()
        assert first.result(timeout=5) is not None

    with sessions() as session:
        delivery = session.scalar(
            select(EventDeliveryModel).where(EventDeliveryModel.event_id == event.id)
        )
        assert delivery is not None
        assert delivery.status == DeliveryStatus.DISPATCHED.value
        assert delivery.attempts == 1
        assert executions == 1


def test_persisted_domain_events_reject_update_and_delete(
    sessions: sessionmaker[Session],
) -> None:
    event = DomainEvent(
        event_type="reservation.created",
        aggregate_id=uuid4(),
        aggregate_type="Reservation",
        producer_module="charging",
        occurred_at=datetime.now(UTC),
        payload={"owner_id": str(uuid4())},
    )
    with sessions() as session:
        EventPublisher(session, ConsumerRegistry()).publish(event)
        session.commit()

    with sessions() as session, pytest.raises(DBAPIError):
        session.execute(
            update(DomainEventModel)
            .where(DomainEventModel.id == event.id)
            .values(event_type="reservation.cancelled")
        )
        session.commit()

    with sessions() as session, pytest.raises(DBAPIError):
        session.execute(delete(DomainEventModel).where(DomainEventModel.id == event.id))
        session.commit()

    with sessions() as session:
        persisted = session.get(DomainEventModel, event.id)
        assert persisted is not None
        assert persisted.event_type == "reservation.created"


def test_administrative_api_authorization_and_filters(
    sessions: sessionmaker[Session], monkeypatch: MonkeyPatch
) -> None:
    suffix = uuid4().hex
    with sessions() as session:
        admin = SqlAlchemyUserRepository(session).add(
            User.create(
                email=f"events-admin-{suffix}@example.com",
                display_name="Events Admin",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.PLATFORM_ADMINISTRATOR],
                facility_ids=[],
            )
        )
        human = SqlAlchemyUserRepository(session).add(
            User.create(
                email=f"events-human-{suffix}@example.com",
                display_name="Events Human",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.EV_DRIVER],
                facility_ids=[],
            )
        )

    consumer = f"api-{uuid4()}"
    registry.register(consumer, lambda _event: None)
    event = DomainEvent(
        event_type="reservation.created",
        aggregate_id=uuid4(),
        aggregate_type="Reservation",
        producer_module="charging",
        occurred_at=datetime.now(UTC),
        payload={"owner_id": str(human.id)},
    )
    with sessions() as session:
        EventPublisher(session).publish(event)
        session.commit()

    def override_get_db() -> Iterator[Session]:
        with sessions() as session:
            yield session

    monkeypatch.setattr("app.main.bootstrap_admin", lambda *_args: None)
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    admin_token, _ = create_access_token(admin)
    human_token, _ = create_access_token(human)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    human_headers = {"Authorization": f"Bearer {human_token}"}

    with TestClient(app) as client:
        assert client.get("/domain-events").status_code == 401
        assert client.get("/domain-events", headers=human_headers).status_code == 403
        response = client.get(
            "/domain-events",
            headers=admin_headers,
            params={
                "event_type": "reservation.created",
                "aggregate_type": "Reservation",
                "aggregate_id": str(event.aggregate_id),
                "producer_module": "charging",
                "consumer": consumer,
                "delivery_status": "DISPATCHED",
                "occurred_from": (event.occurred_at - timedelta(seconds=1)).isoformat(),
                "occurred_to": (event.occurred_at + timedelta(seconds=1)).isoformat(),
                "offset": 0,
                "limit": 1,
            },
        )
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [str(event.id)]
        assert (
            client.get(
                "/domain-events",
                headers=admin_headers,
                params={"event_type": "reservation.cancelled"},
            ).json()
            == []
        )
        detail = client.get(f"/domain-events/{event.id}", headers=admin_headers)
        assert detail.status_code == 200
        assert detail.json()["deliveries"][0]["consumer"] == consumer
