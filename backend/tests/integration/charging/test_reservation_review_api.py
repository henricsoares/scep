from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from app.infrastructure.database import Base, get_db
from app.main import create_app
from app.modules.charging.api.reservations import get_reservation_service
from app.modules.charging.domain.facility import Facility, FacilityStatus, FacilityType
from app.modules.charging.domain.station import (
    ChargingStation,
    ChargingStationStatus,
    ConnectorStatus,
    ConnectorType,
)
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.reservation_model import ReservationModel
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from app.modules.identity.application.security import create_access_token, hash_password
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@dataclass
class ReservationApiContext:
    app: FastAPI
    client: TestClient
    sessions: sessionmaker[Session]
    owner: User
    facility_ids: tuple[UUID, UUID]
    connector_ids: tuple[UUID, UUID, UUID]

    def create_user(
        self,
        email: str,
        *,
        roles: list[HumanRole] | None = None,
        account_type: AccountType = AccountType.HUMAN,
        facility_ids: list[UUID] | None = None,
    ) -> User:
        with self.sessions() as session:
            return SqlAlchemyUserRepository(session).add(
                User.create(
                    email=email,
                    display_name=email.split("@", maxsplit=1)[0],
                    password_hash=hash_password("SecurePassword123!"),
                    account_type=account_type,
                    status=AccountStatus.ACTIVE,
                    roles=roles or [],
                    facility_ids=facility_ids or [],
                )
            )

    @staticmethod
    def headers(user: User) -> dict[str, str]:
        token, _ = create_access_token(user)
        return {"Authorization": f"Bearer {token}"}


def _station(
    session: Session, facility_id: UUID, serial: str, connector_types: list[ConnectorType]
) -> ChargingStation:
    return SqlAlchemyChargingStationRepository(session).add(
        ChargingStation.create(
            facility_id=facility_id,
            name=serial,
            description=None,
            serial_number=serial,
            manufacturer=None,
            model=None,
            maximum_power_kw=100,
            connectors=[
                (connector_type, 22, ConnectorStatus.AVAILABLE)
                for connector_type in connector_types
            ],
        )
    )


@pytest.fixture
def review_context(monkeypatch: MonkeyPatch) -> Iterator[ReservationApiContext]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Iterator[Session]:
        with sessions() as session:
            yield session

    monkeypatch.setattr("app.main.bootstrap_admin", lambda *_args: None)
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with sessions() as session:
        owner = SqlAlchemyUserRepository(session).add(
            User.create(
                email="review-owner@example.com",
                display_name="Review Owner",
                password_hash=hash_password("SecurePassword123!"),
                account_type=AccountType.HUMAN,
                status=AccountStatus.ACTIVE,
                roles=[HumanRole.EV_DRIVER],
                facility_ids=[],
            )
        )
        facilities = tuple(
            SqlAlchemyFacilityRepository(session).add(
                Facility.create(
                    name=f"Review Facility {number}",
                    facility_type=FacilityType.UNIVERSITY,
                    timezone="UTC",
                    country="Brazil",
                    city="Juiz de Fora",
                    address=f"Campus {number}",
                )
            )
            for number in (1, 2)
        )
        first_station = _station(
            session, facilities[0].id, "REVIEW-STATION-1", [ConnectorType.TYPE2, ConnectorType.CCS2]
        )
        second_station = _station(
            session, facilities[1].id, "REVIEW-STATION-2", [ConnectorType.NACS]
        )

    context = ReservationApiContext(
        app=app,
        client=TestClient(app, raise_server_exceptions=False),
        sessions=sessions,
        owner=owner,
        facility_ids=(facilities[0].id, facilities[1].id),
        connector_ids=(
            first_station.connectors[0].id,
            first_station.connectors[1].id,
            second_station.connectors[0].id,
        ),
    )
    with context.client:
        yield context
    Base.metadata.drop_all(engine)


def create_vehicle(
    context: ReservationApiContext, user: User, name: str = "Review EV"
) -> dict[str, Any]:
    response = context.client.post(
        "/vehicles", json={"display_name": name}, headers=context.headers(user)
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def create_reservation(
    context: ReservationApiContext,
    user: User,
    vehicle_id: str,
    connector_id: UUID,
    *,
    start: datetime | None = None,
) -> dict[str, Any]:
    start = start or datetime.now(UTC) + timedelta(hours=4)
    response = context.client.post(
        "/reservations",
        json={
            "vehicle_id": vehicle_id,
            "connector_id": str(connector_id),
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
        },
        headers=context.headers(user),
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_human_owned_workflow_and_resource_semantics(
    review_context: ReservationApiContext,
) -> None:
    context = review_context
    other = context.create_user("review-other@example.com", roles=[HumanRole.EV_DRIVER])
    owned_vehicle = create_vehicle(context, context.owner)
    other_vehicle = create_vehicle(context, other, "Other EV")

    listed = context.client.get("/vehicles", headers=context.headers(context.owner)).json()
    assert [item["id"] for item in listed] == [owned_vehicle["id"]]
    assert (
        context.client.get(
            f"/vehicles/{owned_vehicle['id']}", headers=context.headers(context.owner)
        ).status_code
        == 200
    )
    assert (
        context.client.get(
            f"/vehicles/{other_vehicle['id']}", headers=context.headers(context.owner)
        ).status_code
        == 404
    )

    created = create_reservation(
        context, context.owner, owned_vehicle["id"], context.connector_ids[0]
    )
    concealed_create = context.client.post(
        "/reservations",
        json={
            "vehicle_id": other_vehicle["id"],
            "connector_id": str(context.connector_ids[1]),
            "start_at": (datetime.now(UTC) + timedelta(hours=10)).isoformat(),
            "end_at": (datetime.now(UTC) + timedelta(hours=11)).isoformat(),
        },
        headers=context.headers(context.owner),
    )
    assert concealed_create.status_code == 404
    reservation = created["reservation"]
    assert (
        context.client.get(
            f"/reservations/{reservation['id']}", headers=context.headers(other)
        ).status_code
        == 404
    )
    patched = context.client.patch(
        f"/reservations/{reservation['id']}",
        json={
            "start_at": (datetime.now(UTC) + timedelta(hours=6)).isoformat(),
            "end_at": (datetime.now(UTC) + timedelta(hours=7)).isoformat(),
        },
        headers=context.headers(context.owner),
    )
    assert patched.status_code == 200
    cancelled = context.client.post(
        f"/reservations/{reservation['id']}/cancel",
        headers=context.headers(context.owner),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["warnings"] == []

    missing = str(uuid4())
    payload = {
        "vehicle_id": missing,
        "connector_id": str(context.connector_ids[0]),
        "start_at": (datetime.now(UTC) + timedelta(hours=8)).isoformat(),
        "end_at": (datetime.now(UTC) + timedelta(hours=9)).isoformat(),
    }
    assert (
        context.client.post(
            "/reservations", json=payload, headers=context.headers(context.owner)
        ).status_code
        == 404
    )
    payload["vehicle_id"] = owned_vehicle["id"]
    payload["connector_id"] = missing
    assert (
        context.client.post(
            "/reservations", json=payload, headers=context.headers(context.owner)
        ).status_code
        == 404
    )
    assert (
        context.client.get(
            f"/reservations/{missing}", headers=context.headers(context.owner)
        ).status_code
        == 404
    )


@pytest.mark.parametrize(
    "resource",
    ["connector", "station", "facility", "station_inactive", "facility_inactive"],
)
def test_ineligible_and_missing_infrastructure_status_codes(
    review_context: ReservationApiContext, resource: str
) -> None:
    context = review_context
    vehicle = create_vehicle(context, context.owner)
    with context.sessions() as session:
        connector = session.get(ConnectorModel, context.connector_ids[0])
        assert connector is not None
        station = session.get(ChargingStationModel, connector.charging_station_id)
        assert station is not None
        facility = session.get(FacilityModel, station.facility_id)
        assert facility is not None
        if resource == "connector":
            connector.status = ConnectorStatus.OUT_OF_SERVICE.value
            expected = 422
        elif resource == "station":
            connector.charging_station_id = uuid4()
            expected = 404
        elif resource == "facility":
            station.facility_id = uuid4()
            expected = 404
        elif resource == "station_inactive":
            station.status = ChargingStationStatus.INACTIVE.value
            expected = 422
        else:
            facility.status = FacilityStatus.INACTIVE.value
            expected = 422
        session.commit()

    start = datetime.now(UTC) + timedelta(hours=4)
    response = context.client.post(
        "/reservations",
        json={
            "vehicle_id": vehicle["id"],
            "connector_id": str(context.connector_ids[0]),
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
        },
        headers=context.headers(context.owner),
    )
    assert response.status_code == expected


@pytest.mark.parametrize(
    ("model_name", "field_name"),
    [
        ("vehicle", "display_name"),
        ("vehicle", "status"),
        ("reservation", "vehicle_id"),
        ("reservation", "start_at"),
        ("reservation", "end_at"),
    ],
)
def test_patch_rejects_explicit_null(
    review_context: ReservationApiContext, model_name: str, field_name: str
) -> None:
    context = review_context
    vehicle = create_vehicle(context, context.owner)
    if model_name == "vehicle":
        path = f"/vehicles/{vehicle['id']}"
    else:
        reservation = create_reservation(
            context, context.owner, vehicle["id"], context.connector_ids[0]
        )["reservation"]
        path = f"/reservations/{reservation['id']}"
    response = context.client.patch(
        path, json={field_name: None}, headers=context.headers(context.owner)
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_patch_preserves_omitted_fields_and_rejects_empty_payload(
    review_context: ReservationApiContext,
) -> None:
    context = review_context
    vehicle = create_vehicle(context, context.owner)
    empty = context.client.patch(
        f"/vehicles/{vehicle['id']}", json={}, headers=context.headers(context.owner)
    )
    assert empty.status_code == 422
    renamed_only = context.client.patch(
        f"/vehicles/{vehicle['id']}",
        json={"display_name": "Renamed Once"},
        headers=context.headers(context.owner),
    )
    assert renamed_only.status_code == 200
    assert renamed_only.json()["display_name"] == "Renamed Once"
    assert renamed_only.json()["status"] == "ACTIVE"
    renamed = context.client.patch(
        f"/vehicles/{vehicle['id']}",
        json={"display_name": "Renamed EV", "status": "INACTIVE"},
        headers=context.headers(context.owner),
    )
    assert renamed.status_code == 200
    assert renamed.json()["display_name"] == "Renamed EV"
    assert renamed.json()["status"] == "INACTIVE"


def test_platform_administrator_workflow_preserves_invariants(
    review_context: ReservationApiContext,
) -> None:
    context = review_context
    admin = context.create_user(
        "review-admin@example.com", roles=[HumanRole.PLATFORM_ADMINISTRATOR]
    )
    created_vehicle = context.client.post(
        "/vehicles",
        json={"display_name": "Delegated EV", "owner_id": str(context.owner.id)},
        headers=context.headers(admin),
    )
    assert created_vehicle.status_code == 201
    vehicle = created_vehicle.json()
    assert vehicle["owner_id"] == str(context.owner.id)
    assert (
        context.client.get(f"/vehicles/{vehicle['id']}", headers=context.headers(admin)).status_code
        == 200
    )
    reservation = create_reservation(
        context, context.owner, vehicle["id"], context.connector_ids[0]
    )["reservation"]
    mismatched_owner = context.client.post(
        "/reservations",
        json={
            "owner_id": str(admin.id),
            "vehicle_id": vehicle["id"],
            "connector_id": str(context.connector_ids[1]),
            "start_at": (datetime.now(UTC) + timedelta(hours=10)).isoformat(),
            "end_at": (datetime.now(UTC) + timedelta(hours=11)).isoformat(),
        },
        headers=context.headers(admin),
    )
    assert mismatched_owner.status_code == 422
    assert (
        context.client.get(
            f"/reservations/{reservation['id']}", headers=context.headers(admin)
        ).status_code
        == 200
    )
    rescheduled = context.client.patch(
        f"/reservations/{reservation['id']}",
        json={
            "start_at": (datetime.now(UTC) + timedelta(hours=7)).isoformat(),
            "end_at": (datetime.now(UTC) + timedelta(hours=8)).isoformat(),
        },
        headers=context.headers(admin),
    )
    assert rescheduled.status_code == 200
    assert (
        context.client.post(
            f"/reservations/{reservation['id']}/cancel", headers=context.headers(admin)
        ).status_code
        == 200
    )


def test_facility_operator_has_scoped_read_and_forbidden_mutation(
    review_context: ReservationApiContext,
) -> None:
    context = review_context
    vehicle = create_vehicle(context, context.owner)
    first = create_reservation(context, context.owner, vehicle["id"], context.connector_ids[0])[
        "reservation"
    ]
    second = create_reservation(
        context,
        context.owner,
        vehicle["id"],
        context.connector_ids[2],
        start=datetime.now(UTC) + timedelta(hours=7),
    )["reservation"]
    operator = context.create_user(
        "review-operator@example.com",
        roles=[HumanRole.FACILITY_OPERATOR],
        facility_ids=[context.facility_ids[0]],
    )
    listed = context.client.get("/reservations", headers=context.headers(operator)).json()
    assert [item["id"] for item in listed] == [first["id"]]
    connector_calendar = context.client.get(
        f"/connectors/{context.connector_ids[0]}/reservations",
        headers=context.headers(operator),
    )
    assert connector_calendar.status_code == 200
    assert [item["id"] for item in connector_calendar.json()] == [first["id"]]
    outside_calendar = context.client.get(
        f"/connectors/{context.connector_ids[2]}/reservations",
        headers=context.headers(operator),
    )
    assert outside_calendar.status_code == 200
    assert outside_calendar.json() == []
    assert (
        context.client.get(
            f"/reservations/{second['id']}", headers=context.headers(operator)
        ).status_code
        == 404
    )
    assert (
        context.client.patch(
            f"/reservations/{first['id']}",
            json={"end_at": (datetime.now(UTC) + timedelta(hours=6)).isoformat()},
            headers=context.headers(operator),
        ).status_code
        == 403
    )
    assert (
        context.client.post(
            f"/reservations/{first['id']}/cancel", headers=context.headers(operator)
        ).status_code
        == 403
    )
    start = datetime.now(UTC) + timedelta(hours=10)
    assert (
        context.client.post(
            "/reservations",
            json={
                "vehicle_id": vehicle["id"],
                "connector_id": str(context.connector_ids[0]),
                "start_at": start.isoformat(),
                "end_at": (start + timedelta(hours=1)).isoformat(),
            },
            headers=context.headers(operator),
        ).status_code
        == 404
    )


def test_facility_operator_visibility_combines_ownership_and_facility_scope(
    review_context: ReservationApiContext,
) -> None:
    context = review_context
    operator = context.create_user(
        "review-operator-union@example.com",
        roles=[HumanRole.FACILITY_OPERATOR],
        facility_ids=[context.facility_ids[0]],
    )
    operator_vehicle = create_vehicle(context, operator, "Operator EV")
    other_vehicle = create_vehicle(context, context.owner, "Other Owner EV")
    start = datetime.now(UTC) + timedelta(hours=4)

    owned_outside_scope = create_reservation(
        context,
        operator,
        operator_vehicle["id"],
        context.connector_ids[2],
        start=start,
    )["reservation"]
    managed_facility = create_reservation(
        context,
        context.owner,
        other_vehicle["id"],
        context.connector_ids[0],
        start=start + timedelta(hours=2),
    )["reservation"]
    concealed = create_reservation(
        context,
        context.owner,
        other_vehicle["id"],
        context.connector_ids[2],
        start=start + timedelta(hours=4),
    )["reservation"]

    listed = context.client.get("/reservations", headers=context.headers(operator))
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [
        owned_outside_scope["id"],
        managed_facility["id"],
    ]
    assert (
        context.client.get(
            f"/reservations/{owned_outside_scope['id']}",
            headers=context.headers(operator),
        ).status_code
        == 200
    )
    assert (
        context.client.get(
            f"/reservations/{managed_facility['id']}",
            headers=context.headers(operator),
        ).status_code
        == 200
    )
    assert (
        context.client.get(
            f"/reservations/{concealed['id']}", headers=context.headers(operator)
        ).status_code
        == 404
    )


def test_technical_client_and_read_only_roles_keep_owned_scope(
    review_context: ReservationApiContext,
) -> None:
    context = review_context
    technical = context.create_user(
        "review-technical@example.com", account_type=AccountType.TECHNICAL_CLIENT
    )
    technical_vehicle = create_vehicle(context, technical, "Synthetic EV")
    technical_reservation = create_reservation(
        context, technical, technical_vehicle["id"], context.connector_ids[0]
    )["reservation"]
    assert context.client.get("/vehicles", headers=context.headers(technical)).status_code == 200
    assert (
        context.client.get(
            f"/reservations/{technical_reservation['id']}", headers=context.headers(technical)
        ).status_code
        == 200
    )
    technical_reschedule = context.client.patch(
        f"/reservations/{technical_reservation['id']}",
        json={
            "start_at": (datetime.now(UTC) + timedelta(hours=7)).isoformat(),
            "end_at": (datetime.now(UTC) + timedelta(hours=8)).isoformat(),
        },
        headers=context.headers(technical),
    )
    assert technical_reschedule.status_code == 200
    assert (
        context.client.post(
            f"/reservations/{technical_reservation['id']}/cancel",
            headers=context.headers(technical),
        ).status_code
        == 200
    )
    assert (
        context.client.post(
            "/facilities",
            json={
                "name": "Forbidden Technical Facility",
                "facility_type": "University",
                "timezone": "UTC",
                "country": "Brazil",
                "city": "Juiz de Fora",
                "address": "Campus",
            },
            headers=context.headers(technical),
        ).status_code
        == 403
    )

    owner_vehicle = create_vehicle(context, context.owner)
    owner_reservation = create_reservation(
        context,
        context.owner,
        owner_vehicle["id"],
        context.connector_ids[1],
        start=datetime.now(UTC) + timedelta(hours=7),
    )["reservation"]
    assert (
        context.client.get(
            f"/vehicles/{owner_vehicle['id']}", headers=context.headers(technical)
        ).status_code
        == 404
    )
    assert (
        context.client.get(
            f"/reservations/{owner_reservation['id']}", headers=context.headers(technical)
        ).status_code
        == 404
    )
    for number, role in enumerate((HumanRole.RESEARCHER, HumanRole.DATA_SCIENTIST), start=1):
        actor = context.create_user(f"review-readonly-{number}@example.com", roles=[role])
        own_vehicle = create_vehicle(context, actor, f"Owned Research EV {number}")
        own_reservation = create_reservation(
            context,
            actor,
            own_vehicle["id"],
            context.connector_ids[2],
            start=datetime.now(UTC) + timedelta(hours=10 + number * 2),
        )["reservation"]
        listed = context.client.get("/reservations", headers=context.headers(actor)).json()
        assert [item["id"] for item in listed] == [own_reservation["id"]]
        assert (
            context.client.get(
                f"/reservations/{owner_reservation['id']}", headers=context.headers(actor)
            ).status_code
            == 404
        )


def test_reservation_warnings_filters_pagination_and_no_show(
    review_context: ReservationApiContext,
) -> None:
    context = review_context
    first_vehicle = create_vehicle(context, context.owner, "First EV")
    second_vehicle = create_vehicle(context, context.owner, "Second EV")
    start = datetime.now(UTC) + timedelta(hours=4)
    first = create_reservation(
        context, context.owner, first_vehicle["id"], context.connector_ids[0], start=start
    )
    back_to_back = create_reservation(
        context,
        context.owner,
        second_vehicle["id"],
        context.connector_ids[0],
        start=start + timedelta(hours=1),
    )
    assert back_to_back["warnings"][0]["code"] == "BACK_TO_BACK_RESERVATION"

    connector_conflict = context.client.post(
        "/reservations",
        json={
            "vehicle_id": second_vehicle["id"],
            "connector_id": str(context.connector_ids[0]),
            "start_at": (start + timedelta(minutes=30)).isoformat(),
            "end_at": (start + timedelta(hours=1, minutes=30)).isoformat(),
        },
        headers=context.headers(context.owner),
    )
    assert connector_conflict.status_code == 409
    assert connector_conflict.json()["detail"]["code"] == "CONNECTOR_RESERVATION_CONFLICT"
    vehicle_conflict = context.client.post(
        "/reservations",
        json={
            "vehicle_id": first_vehicle["id"],
            "connector_id": str(context.connector_ids[1]),
            "start_at": (start + timedelta(minutes=15)).isoformat(),
            "end_at": (start + timedelta(minutes=45)).isoformat(),
        },
        headers=context.headers(context.owner),
    )
    assert vehicle_conflict.status_code == 409
    assert vehicle_conflict.json()["detail"]["code"] == "VEHICLE_RESERVATION_CONFLICT"

    page = context.client.get(
        "/reservations?status=CONFIRMED&offset=1&limit=1",
        headers=context.headers(context.owner),
    )
    assert page.status_code == 200
    assert len(page.json()) == 1

    late_start = datetime.now(UTC) + timedelta(minutes=30)
    late = create_reservation(
        context,
        context.owner,
        second_vehicle["id"],
        context.connector_ids[1],
        start=late_start,
    )["reservation"]
    late_cancel = context.client.post(
        f"/reservations/{late['id']}/cancel", headers=context.headers(context.owner)
    )
    assert late_cancel.status_code == 200
    assert late_cancel.json()["warnings"][0]["code"] == "LATE_CANCELLATION"

    with context.sessions() as session:
        model = session.get(ReservationModel, UUID(first["reservation"]["id"]))
        assert model is not None
        model.start_at = datetime.now(UTC) - timedelta(minutes=16)
        model.end_at = datetime.now(UTC) + timedelta(minutes=44)
        session.commit()
    reconciled = context.client.get(
        f"/reservations/{first['reservation']['id']}", headers=context.headers(context.owner)
    )
    assert reconciled.status_code == 200
    assert reconciled.json()["status"] == "NO_SHOW"


def test_reschedule_early_start_boundary_and_terminal_state(
    review_context: ReservationApiContext,
) -> None:
    context = review_context
    vehicle = create_vehicle(context, context.owner)
    boundary = create_reservation(
        context,
        context.owner,
        vehicle["id"],
        context.connector_ids[0],
        start=datetime.now(UTC) + timedelta(hours=4),
    )["reservation"]
    with context.sessions() as session:
        model = session.get(ReservationModel, UUID(boundary["id"]))
        assert model is not None
        model.start_at = datetime.now(UTC) + timedelta(minutes=15)
        model.end_at = model.start_at + timedelta(hours=1)
        session.commit()
    at_boundary = context.client.patch(
        f"/reservations/{boundary['id']}",
        json={"end_at": (datetime.now(UTC) + timedelta(hours=2)).isoformat()},
        headers=context.headers(context.owner),
    )
    assert at_boundary.status_code == 422

    terminal = create_reservation(
        context,
        context.owner,
        vehicle["id"],
        context.connector_ids[1],
        start=datetime.now(UTC) + timedelta(hours=7),
    )["reservation"]
    cancelled = context.client.post(
        f"/reservations/{terminal['id']}/cancel",
        headers=context.headers(context.owner),
    )
    assert cancelled.status_code == 200
    rejected = context.client.patch(
        f"/reservations/{terminal['id']}",
        json={"end_at": (datetime.now(UTC) + timedelta(hours=9)).isoformat()},
        headers=context.headers(context.owner),
    )
    assert rejected.status_code == 422


def test_unexpected_database_failure_uses_internal_error_path(
    review_context: ReservationApiContext,
) -> None:
    context = review_context

    class FailingService:
        def create(self, **_kwargs: object) -> object:
            raise DBAPIError("redacted", {}, RuntimeError("connection failed"), False)

    context.app.dependency_overrides[get_reservation_service] = lambda: FailingService()
    start = datetime.now(UTC) + timedelta(hours=4)
    response = context.client.post(
        "/reservations",
        json={
            "vehicle_id": str(uuid4()),
            "connector_id": str(uuid4()),
            "start_at": start.isoformat(),
            "end_at": (start + timedelta(hours=1)).isoformat(),
        },
        headers=context.headers(context.owner),
    )
    context.app.dependency_overrides.pop(get_reservation_service)
    assert response.status_code == 500
    assert "connection failed" not in response.text
