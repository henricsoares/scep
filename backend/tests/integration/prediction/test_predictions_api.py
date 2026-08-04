from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from app.infrastructure.database import Base, get_db
from app.modules.charging.infrastructure import charging_session_model
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.charging.infrastructure.reservation_model import ReservationModel
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel
from app.modules.datasets.infrastructure import DatasetExportModel
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.domain.user import (
    AccountStatus,
    AccountType,
    HumanRole,
    TechnicalClientProfile,
    User,
)
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from app.modules.prediction.api import router as prediction_router
from app.modules.prediction.infrastructure import (
    WeeklyOccupancyPredictionBucketModel,
    WeeklyOccupancyPredictionCurrentModel,
    WeeklyOccupancyPredictionPublicationModel,
)
from app.modules.prediction.metrics import (
    authorization_failures_total,
    bucket_validation_failures_total,
    publication_duration_seconds,
    publication_outcomes_total,
    queries_total,
    recommendations_total,
)
from app.modules.simulation import infrastructure as simulation_infrastructure
from fastapi import FastAPI
from fastapi.testclient import TestClient
from prometheus_client import generate_latest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

_ = charging_session_model, simulation_infrastructure


@dataclass
class PredictionContext:
    client: TestClient
    app: FastAPI
    sessions: sessionmaker[Session]
    actors: dict[str, User]
    actor: dict[str, User]
    facilities: tuple[UUID, UUID]
    stations: tuple[UUID, UUID]
    connectors: tuple[UUID, UUID, UUID]

    def use(self, name: str) -> None:
        self.actor["current"] = self.actors[name]


def _facility(
    *, timezone: str, status: str = "Active", operating_hours: dict[str, Any] | None = None
) -> FacilityModel:
    identifier = uuid4()
    return FacilityModel(
        id=identifier,
        name=f"Prediction Facility {identifier}",
        facility_type="University",
        timezone=timezone,
        country="Brazil",
        city="Juiz de Fora",
        address="Campus",
        operating_hours=operating_hours,
        status=status,
    )


def _station(facility_id: UUID, *, status: str = "Active") -> ChargingStationModel:
    identifier = uuid4()
    return ChargingStationModel(
        id=identifier,
        facility_id=facility_id,
        name=f"Station {identifier}",
        serial_number=str(identifier),
        maximum_power_kw=50,
        status=status,
    )


def _connector(station_id: UUID, *, status: str = "Available") -> ConnectorModel:
    return ConnectorModel(
        id=uuid4(),
        charging_station_id=station_id,
        connector_type="CCS2",
        maximum_power_kw=50,
        status=status,
    )


def _user(
    email: str,
    *,
    roles: list[HumanRole] | None = None,
    account_type: AccountType = AccountType.HUMAN,
    profile: TechnicalClientProfile | None = None,
    facility_ids: list[UUID] | None = None,
    status: AccountStatus = AccountStatus.ACTIVE,
) -> User:
    return User.create(
        email=email,
        display_name=email.split("@", maxsplit=1)[0],
        password_hash="test-password-hash",
        account_type=account_type,
        technical_profile=profile,
        status=status,
        roles=roles or [],
        facility_ids=facility_ids or [],
    )


@pytest.fixture
def context() -> Iterator[PredictionContext]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with sessions() as db:
        sao_paulo = _facility(timezone="America/Sao_Paulo")
        los_angeles = _facility(timezone="America/Los_Angeles")
        station_one = _station(sao_paulo.id)
        station_two = _station(los_angeles.id)
        connector_one = _connector(station_one.id)
        connector_two = _connector(station_one.id)
        connector_three = _connector(station_two.id)
        db.add_all(
            [
                sao_paulo,
                los_angeles,
                station_one,
                station_two,
                connector_one,
                connector_two,
                connector_three,
            ]
        )
        db.commit()
        users = SqlAlchemyUserRepository(db)
        actors = {
            "admin": users.add(
                _user("prediction-admin@example.com", roles=[HumanRole.PLATFORM_ADMINISTRATOR])
            ),
            "scientist": users.add(
                _user("prediction-scientist@example.com", roles=[HumanRole.DATA_SCIENTIST])
            ),
            "ai": users.add(
                _user(
                    "prediction-ai@example.com",
                    account_type=AccountType.TECHNICAL_CLIENT,
                    profile=TechnicalClientProfile.AI_RESEARCH_ENVIRONMENT,
                )
            ),
            "technical": users.add(
                _user("prediction-technical@example.com", account_type=AccountType.TECHNICAL_CLIENT)
            ),
            "researcher": users.add(
                _user("prediction-researcher@example.com", roles=[HumanRole.RESEARCHER])
            ),
            "operator": users.add(
                _user(
                    "prediction-operator@example.com",
                    roles=[HumanRole.FACILITY_OPERATOR],
                    facility_ids=[sao_paulo.id],
                )
            ),
            "driver": users.add(
                _user("prediction-driver@example.com", roles=[HumanRole.EV_DRIVER])
            ),
        }

    actor = {"current": actors["admin"]}
    app = FastAPI()
    app.include_router(prediction_router)

    def override_db() -> Iterator[Session]:
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[current_user] = lambda: actor["current"]
    client = TestClient(app)
    yield PredictionContext(
        client=client,
        app=app,
        sessions=sessions,
        actors=actors,
        actor=actor,
        facilities=(sao_paulo.id, los_angeles.id),
        stations=(station_one.id, station_two.id),
        connectors=(connector_one.id, connector_two.id, connector_three.id),
    )
    client.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def _buckets(
    *, base: float = 0.25, overrides: dict[tuple[str, int], float] | None = None
) -> list[dict[str, Any]]:
    overrides = overrides or {}
    weekdays = (
        "MONDAY",
        "TUESDAY",
        "WEDNESDAY",
        "THURSDAY",
        "FRIDAY",
        "SATURDAY",
        "SUNDAY",
    )
    return [
        {
            "day_of_week": day,
            "hour_of_day": hour,
            "expected_occupancy_rate": overrides.get((day, hour), base),
        }
        for day in weekdays
        for hour in range(24)
    ]


def _payload(
    context: PredictionContext,
    *,
    scope_type: str = "CONNECTOR",
    facility_index: int = 0,
    connector_index: int = 0,
    external_run_id: str | None = None,
    generated_at: str = "2026-08-01T12:00:00Z",
    buckets: list[dict[str, Any]] | None = None,
    dataset_export_id: UUID | None = None,
) -> dict[str, Any]:
    facility_id = context.facilities[facility_index]
    station_id = context.stations[facility_index]
    connector_id = context.connectors[connector_index]
    result: dict[str, Any] = {
        "contract_version": "1.0",
        "prediction_type": "WEEKLY_OCCUPANCY",
        "scope_type": scope_type,
        "facility_id": str(facility_id),
        "timezone": "America/Sao_Paulo" if facility_index == 0 else "America/Los_Angeles",
        "model_name": "weekly-effective-occupancy",
        "model_version": "1.0.0",
        "external_run_id": external_run_id or f"run-{uuid4()}",
        "generated_at": generated_at,
        "dataset_export_id": str(dataset_export_id) if dataset_export_id else None,
        "training_data_from": "2026-05-01T00:00:00Z",
        "training_data_to": "2026-07-31T00:00:00Z",
        "buckets": buckets or _buckets(),
    }
    if scope_type in {"STATION", "CONNECTOR"}:
        result["station_id"] = str(station_id)
    if scope_type == "CONNECTOR":
        result["connector_id"] = str(connector_id)
    return result


def _publish(context: PredictionContext, **kwargs: Any) -> dict[str, Any]:
    response = context.client.post(
        "/predictions/weekly-occupancy-publications",
        json=_payload(context, **kwargs),
        headers={"X-Request-ID": "prediction-test"},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


def test_valid_facility_station_and_connector_publications_are_atomic_and_ordered(
    context: PredictionContext,
) -> None:
    facility = _publish(context, scope_type="FACILITY")
    station = _publish(context, scope_type="STATION")
    connector = _publish(
        context,
        scope_type="CONNECTOR",
        buckets=list(reversed(_buckets())),
    )

    assert {
        facility["scope"]["scope_type"],
        station["scope"]["scope_type"],
        connector["scope"]["scope_type"],
    } == {
        "FACILITY",
        "STATION",
        "CONNECTOR",
    }
    profile = context.client.get(
        f"/predictions/weekly-occupancy-publications/{connector['id']}/profile"
    )
    assert profile.status_code == 200
    assert profile.json()["bucket_count"] == 168
    assert profile.json()["buckets"][0]["day_of_week"] == "MONDAY"
    assert profile.json()["buckets"][0]["hour_of_day"] == 0
    assert profile.json()["buckets"][-1]["day_of_week"] == "SUNDAY"
    assert profile.json()["buckets"][-1]["hour_of_day"] == 23
    with context.sessions() as db:
        assert (
            db.scalar(select(func.count()).select_from(WeeklyOccupancyPredictionPublicationModel))
            == 3
        )
        assert (
            db.scalar(select(func.count()).select_from(WeeklyOccupancyPredictionBucketModel)) == 504
        )
        assert (
            db.scalar(select(func.count()).select_from(WeeklyOccupancyPredictionCurrentModel)) == 3
        )


def test_invalid_profiles_and_hierarchy_write_nothing(context: PredictionContext) -> None:
    invalid_profiles = [
        _buckets()[:-1],
        _buckets() + [_buckets()[0]],
    ]
    duplicate = _buckets()
    duplicate[-1] = duplicate[0]
    invalid_profiles.append(duplicate)
    for invalid in invalid_profiles:
        response = context.client.post(
            "/predictions/weekly-occupancy-publications",
            json=_payload(context, buckets=invalid),
        )
        assert response.status_code == 422

    numeric_string = _buckets()
    numeric_string[0]["expected_occupancy_rate"] = "0.2"
    assert (
        context.client.post(
            "/predictions/weekly-occupancy-publications",
            json=_payload(context, buckets=numeric_string),
        ).status_code
        == 422
    )

    for field, value in (
        ("day_of_week", "FUNDAY"),
        ("hour_of_day", 24),
        ("expected_occupancy_rate", -0.01),
        ("expected_occupancy_rate", 1.01),
    ):
        invalid_bucket = _buckets()
        invalid_bucket[0][field] = value
        assert (
            context.client.post(
                "/predictions/weekly-occupancy-publications",
                json=_payload(context, buckets=invalid_bucket),
            ).status_code
            == 422
        )

    wrong_station = _payload(context)
    wrong_station["station_id"] = str(context.stations[1])
    mismatch = context.client.post("/predictions/weekly-occupancy-publications", json=wrong_station)
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"]["code"] == "PREDICTION_HIERARCHY_MISMATCH"

    wrong_timezone = _payload(context)
    wrong_timezone["timezone"] = "UTC"
    mismatch = context.client.post(
        "/predictions/weekly-occupancy-publications", json=wrong_timezone
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"]["code"] == "PREDICTION_TIMEZONE_MISMATCH"

    wrong_connector = _payload(context)
    wrong_connector["connector_id"] = str(context.connectors[2])
    mismatch = context.client.post(
        "/predictions/weekly-occupancy-publications", json=wrong_connector
    )
    assert mismatch.status_code == 400
    assert mismatch.json()["detail"]["code"] == "PREDICTION_HIERARCHY_MISMATCH"

    missing = _payload(context)
    missing["connector_id"] = str(uuid4())
    assert (
        context.client.post("/predictions/weekly-occupancy-publications", json=missing).status_code
        == 404
    )

    with context.sessions() as db:
        facility = db.get(FacilityModel, context.facilities[0])
        assert facility is not None
        facility.status = "Inactive"
        db.commit()
    ineligible = context.client.post(
        "/predictions/weekly-occupancy-publications", json=_payload(context)
    )
    assert ineligible.status_code == 400
    assert ineligible.json()["detail"]["code"] == "PREDICTION_SCOPE_INELIGIBLE"
    with context.sessions() as db:
        assert (
            db.scalar(select(func.count()).select_from(WeeklyOccupancyPredictionPublicationModel))
            == 0
        )
        assert (
            db.scalar(select(func.count()).select_from(WeeklyOccupancyPredictionBucketModel)) == 0
        )


def test_idempotency_and_generated_time_current_selection(context: PredictionContext) -> None:
    identity = "stable-external-run"
    payload = _payload(context, external_run_id=identity)
    first = context.client.post("/predictions/weekly-occupancy-publications", json=payload)
    assert first.status_code == 201
    replay = context.client.post(
        "/predictions/weekly-occupancy-publications",
        json={**payload, "buckets": list(reversed(payload["buckets"]))},
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["accepted_at"] == first.json()["accepted_at"]
    assert replay.json()["idempotent_replay"] is True

    conflict_buckets = _buckets(base=0.4)
    conflict = context.client.post(
        "/predictions/weekly-occupancy-publications",
        json={**payload, "buckets": conflict_buckets},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "PREDICTION_IDEMPOTENCY_CONFLICT"

    later = _publish(
        context,
        external_run_id="later",
        generated_at="2026-08-03T12:00:00Z",
    )
    earlier = _publish(
        context,
        external_run_id="earlier",
        generated_at="2026-07-30T12:00:00Z",
    )
    equal = _publish(
        context,
        external_run_id="equal",
        generated_at="2026-08-03T12:00:00+00:00",
    )
    assert later["is_current"] is True
    assert earlier["is_current"] is False
    assert equal["is_current"] is False
    current = context.client.get(
        "/predictions/weekly-occupancy-publications/current",
        params={
            "scope_type": "CONNECTOR",
            "facility_id": str(context.facilities[0]),
            "station_id": str(context.stations[0]),
            "connector_id": str(context.connectors[0]),
        },
    )
    assert current.status_code == 200
    assert current.json()["id"] == later["id"]
    history = context.client.get(
        "/predictions/weekly-occupancy-publications",
        params={"facility_id": str(context.facilities[0]), "limit": 2},
    )
    assert history.status_code == 200
    assert history.json()["total"] == 4
    assert len(history.json()["items"]) == 2


def test_authorization_uses_final_capabilities_and_authenticated_publisher(
    context: PredictionContext,
) -> None:
    for actor in ("admin", "scientist", "ai"):
        context.use(actor)
        result = _publish(context, external_run_id=f"authorized-{actor}")
        assert result["publisher_subject_id"] == str(context.actors[actor].id)

    for actor in ("technical", "researcher", "operator", "driver"):
        context.use(actor)
        response = context.client.post(
            "/predictions/weekly-occupancy-publications",
            json=_payload(context, external_run_id=f"denied-{actor}"),
        )
        assert response.status_code == 403

    context.use("scientist")
    spoofed = _payload(context)
    spoofed["publisher_subject_id"] = str(context.actors["admin"].id)
    assert (
        context.client.post("/predictions/weekly-occupancy-publications", json=spoofed).status_code
        == 422
    )

    inactive = replace(context.actors["scientist"], status=AccountStatus.INACTIVE)
    context.actor["current"] = inactive
    assert (
        context.client.post(
            "/predictions/weekly-occupancy-publications", json=_payload(context)
        ).status_code
        == 403
    )

    additive = replace(
        context.actors["scientist"],
        id=uuid4(),
        email="prediction-additive@example.com",
        roles=(HumanRole.EV_DRIVER, HumanRole.DATA_SCIENTIST),
    )
    with context.sessions() as db:
        additive = SqlAlchemyUserRepository(db).add(additive)
    context.actor["current"] = additive
    assert _publish(context, external_run_id="additive-role")["publisher_subject_id"] == str(
        additive.id
    )


@pytest.mark.parametrize("actor", ["researcher", "operator", "driver", "technical"])
def test_publication_authorization_precedes_domain_bucket_validation(
    context: PredictionContext, actor: str
) -> None:
    context.use(actor)

    valid = context.client.post(
        "/predictions/weekly-occupancy-publications",
        json=_payload(context, external_run_id=f"unauthorized-valid-{actor}"),
    )
    assert valid.status_code == 403
    assert valid.json()["detail"]["code"] == "PREDICTION_FORBIDDEN"

    duplicate_buckets = _buckets()
    duplicate_buckets[-1] = duplicate_buckets[0]
    duplicate = context.client.post(
        "/predictions/weekly-occupancy-publications",
        json=_payload(
            context,
            external_run_id=f"unauthorized-duplicate-{actor}",
            buckets=duplicate_buckets,
        ),
    )
    assert duplicate.status_code == 403
    assert duplicate.json()["detail"]["code"] == "PREDICTION_FORBIDDEN"


def test_request_model_validation_remains_a_framework_boundary(
    context: PredictionContext,
) -> None:
    context.use("driver")
    incomplete = context.client.post(
        "/predictions/weekly-occupancy-publications",
        json=_payload(context, buckets=_buckets()[:-1]),
    )
    assert incomplete.status_code == 422
    assert incomplete.json()["detail"][0]["type"] == "too_short"


def test_publication_rejection_metrics_are_counted_once(context: PredictionContext) -> None:
    def rejected_duration_count() -> float:
        child = publication_duration_seconds.labels("rejected")
        metric = next(iter(child.collect()))
        return float(
            next(sample.value for sample in metric.samples if sample.name.endswith("_count"))
        )

    scope_type = "CONNECTOR"
    forbidden_before = authorization_failures_total.labels("publish")._value.get()
    rejected_before = publication_outcomes_total.labels("rejected", scope_type)._value.get()
    duplicate_before = bucket_validation_failures_total.labels(
        "PREDICTION_BUCKET_DUPLICATE"
    )._value.get()
    duration_before = rejected_duration_count()

    duplicate_buckets = _buckets()
    duplicate_buckets[-1] = duplicate_buckets[0]
    context.use("driver")
    forbidden = context.client.post(
        "/predictions/weekly-occupancy-publications",
        json=_payload(context, buckets=duplicate_buckets),
    )
    assert forbidden.status_code == 403
    assert authorization_failures_total.labels("publish")._value.get() == forbidden_before + 1
    assert (
        publication_outcomes_total.labels("rejected", scope_type)._value.get()
        == rejected_before + 1
    )
    assert (
        bucket_validation_failures_total.labels("PREDICTION_BUCKET_DUPLICATE")._value.get()
        == duplicate_before
    )
    assert rejected_duration_count() == duration_before + 1

    context.use("scientist")
    invalid = context.client.post(
        "/predictions/weekly-occupancy-publications",
        json=_payload(context, buckets=duplicate_buckets),
    )
    assert invalid.status_code == 422
    assert authorization_failures_total.labels("publish")._value.get() == forbidden_before + 1
    assert (
        publication_outcomes_total.labels("rejected", scope_type)._value.get()
        == rejected_before + 2
    )
    assert (
        bucket_validation_failures_total.labels("PREDICTION_BUCKET_DUPLICATE")._value.get()
        == duplicate_before + 1
    )
    assert rejected_duration_count() == duration_before + 1


def _dataset(
    context: PredictionContext,
    *,
    owner: User,
    profile: str = "RESEARCH",
    status: str = "COMPLETED",
    facility_id: UUID | None = None,
    expired: bool = False,
) -> UUID:
    identifier = uuid4()
    now = datetime.now(UTC)
    with context.sessions() as db:
        db.add(
            DatasetExportModel(
                id=identifier,
                requested_by=owner.id,
                dataset_type="ANALYTICAL_OCCUPANCY",
                export_profile=profile,
                format="CSV",
                filters={
                    "facility_id": str(facility_id or context.facilities[0]),
                    "station_id": None,
                    "connector_id": None,
                    "from": "2026-05-01T00:00:00Z",
                    "to": "2026-08-01T00:00:00Z",
                    "timezone": "America/Sao_Paulo",
                    "granularity": "hour",
                },
                status=status,
                schema_version="1.0.0",
                created_at=now,
                started_at=now if status != "PENDING" else None,
                data_cutoff_at=now if status != "PENDING" else None,
                completed_at=now if status == "COMPLETED" else None,
                artifact_storage_key="artifact.zip" if status == "COMPLETED" else None,
                artifact_expires_at=(
                    (now - timedelta(days=1) if expired else now + timedelta(days=1))
                    if status == "COMPLETED"
                    else None
                ),
            )
        )
        db.commit()
    return identifier


def test_dataset_export_provenance_uses_owned_research_contract_and_survives_expiry(
    context: PredictionContext,
) -> None:
    context.use("scientist")
    valid = _dataset(context, owner=context.actors["scientist"], expired=True)
    published = _publish(context, dataset_export_id=valid)
    assert published["dataset_export_id"] == str(valid)

    invalid = [
        _dataset(context, owner=context.actors["scientist"], profile="ADMINISTRATIVE"),
        _dataset(context, owner=context.actors["scientist"], status="PENDING"),
        _dataset(context, owner=context.actors["admin"]),
        _dataset(
            context,
            owner=context.actors["scientist"],
            facility_id=context.facilities[1],
        ),
    ]
    for export_id in invalid:
        response = context.client.post(
            "/predictions/weekly-occupancy-publications",
            json=_payload(context, dataset_export_id=export_id),
        )
        assert response.status_code in {400, 403}

    nonexistent = context.client.post(
        "/predictions/weekly-occupancy-publications",
        json=_payload(context, dataset_export_id=uuid4()),
    )
    assert nonexistent.status_code == 400
    assert nonexistent.json()["detail"]["code"] == "PREDICTION_DATASET_EXPORT_INVALID"

    invalid_window = _payload(context)
    invalid_window["training_data_to"] = invalid_window["training_data_from"]
    assert (
        context.client.post(
            "/predictions/weekly-occupancy-publications", json=invalid_window
        ).status_code
        == 400
    )


def test_facility_operator_visibility_and_evdriver_point_lookup(context: PredictionContext) -> None:
    context.use("admin")
    first = _publish(context, external_run_id="operator-visible")
    second = _publish(
        context,
        facility_index=1,
        connector_index=2,
        external_run_id="operator-hidden",
    )
    context.use("operator")
    visible = context.client.get(f"/predictions/weekly-occupancy-publications/{first['id']}")
    assert visible.status_code == 200
    assert "model_name" not in visible.json()
    assert "publisher_subject_id" not in visible.json()
    assert (
        context.client.get(f"/predictions/weekly-occupancy-publications/{second['id']}").status_code
        == 404
    )

    context.use("driver")
    point = context.client.get(
        "/predictions/weekly-occupancy/point",
        params={
            "scope_type": "CONNECTOR",
            "facility_id": str(context.facilities[0]),
            "station_id": str(context.stations[0]),
            "connector_id": str(context.connectors[0]),
            "timestamp": "2026-08-04T21:15:00Z",
        },
    )
    assert point.status_code == 200
    assert point.json()["day_of_week"] == "TUESDAY"
    assert point.json()["hour_of_day"] == 18
    assert point.json()["timezone"] == "America/Sao_Paulo"
    assert point.json()["availability_guaranteed"] is False
    assert "publication_id" not in point.json()


def test_cross_facility_recommendation_resolves_each_timezone_and_ranks_deterministically(
    context: PredictionContext,
) -> None:
    context.use("admin")
    _publish(
        context,
        connector_index=0,
        external_run_id="recommend-sp-one",
        buckets=_buckets(overrides={("TUESDAY", 18): 0.20}),
    )
    _publish(
        context,
        connector_index=1,
        external_run_id="recommend-sp-two",
        buckets=_buckets(overrides={("TUESDAY", 18): 0.20}),
    )
    _publish(
        context,
        facility_index=1,
        connector_index=2,
        external_run_id="recommend-la",
        buckets=_buckets(overrides={("TUESDAY", 14): 0.10}),
    )
    context.use("driver")
    response = context.client.get(
        "/predictions/weekly-occupancy/recommendations/connectors",
        params={"timestamp": "2026-08-04T21:00:00Z"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "resolved_time" not in body
    assert body["total"] == 3
    assert body["items"][0]["facility_id"] == str(context.facilities[1])
    resolved = {item["facility_id"]: item["resolved_time"] for item in body["items"]}
    assert resolved[str(context.facilities[0])] == {
        "day_of_week": "TUESDAY",
        "hour_of_day": 18,
        "timezone": "America/Sao_Paulo",
    }
    assert resolved[str(context.facilities[1])] == {
        "day_of_week": "TUESDAY",
        "hour_of_day": 14,
        "timezone": "America/Los_Angeles",
    }
    tied = [
        item["connector_id"]
        for item in body["items"]
        if item["facility_id"] == str(context.facilities[0])
    ]
    assert tied == sorted(tied)
    with context.sessions() as db:
        assert db.scalar(select(func.count()).select_from(ReservationModel)) == 0

    local = context.client.get(
        "/predictions/weekly-occupancy/recommendations/connectors",
        params={"day_of_week": "TUESDAY", "hour_of_day": 18},
    )
    assert local.status_code == 200
    assert "resolved_time" not in local.json()
    assert all(item["resolved_time"]["hour_of_day"] == 18 for item in local.json()["items"])


def test_station_recommendation_shared_timezone_and_operational_exclusion(
    context: PredictionContext,
) -> None:
    context.use("admin")
    _publish(context, connector_index=0, external_run_id="station-one")
    _publish(context, connector_index=1, external_run_id="station-two")
    with context.sessions() as db:
        second = db.get(ConnectorModel, context.connectors[1])
        assert second is not None
        second.status = "OutOfService"
        db.commit()
    context.use("driver")
    response = context.client.get(
        f"/predictions/weekly-occupancy/recommendations/stations/{context.stations[0]}/connectors",
        params={"day_of_week": "MONDAY", "hour_of_day": 8},
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["resolved_time"]["timezone"] == "America/Sao_Paulo"
    assert response.json()["reservation_created"] is False


def test_openapi_observability_and_missing_current_contract(context: PredictionContext) -> None:
    schema = context.app.openapi()
    paths = schema["paths"]
    for path in (
        "/predictions/weekly-occupancy-publications",
        "/predictions/weekly-occupancy-publications/current",
        "/predictions/weekly-occupancy-publications/{publication_id}",
        "/predictions/weekly-occupancy-publications/{publication_id}/profile",
        "/predictions/weekly-occupancy/point",
        "/predictions/weekly-occupancy/recommendations/connectors",
        "/predictions/weekly-occupancy/recommendations/stations/{station_id}/connectors",
    ):
        assert path in paths
    publication_resource = paths["/predictions/weekly-occupancy-publications/{publication_id}"]
    assert "put" not in publication_resource
    assert "patch" not in publication_resource
    assert "delete" not in publication_resource
    request_schema = schema["components"]["schemas"]["PublishWeeklyOccupancyRequest"]
    bucket_schema = request_schema["properties"]["buckets"]
    assert bucket_schema["minItems"] == 168
    assert bucket_schema["maxItems"] == 168

    missing = context.client.get(
        "/predictions/weekly-occupancy-publications/current",
        params={
            "scope_type": "FACILITY",
            "facility_id": str(context.facilities[0]),
        },
        headers={"X-Request-ID": "missing-current"},
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == {
        "code": "PREDICTION_CURRENT_NOT_FOUND",
        "message": "No current publication exists for this prediction scope.",
        "request_id": "missing-current",
    }
    metrics = generate_latest().decode()
    assert "scep_prediction_missing_current_total" in metrics
    for collector in (publication_outcomes_total, queries_total, recommendations_total):
        assert "publication_id" not in collector._labelnames
        assert "user_id" not in collector._labelnames
        assert "facility_id" not in collector._labelnames
        assert "external_run_id" not in collector._labelnames
