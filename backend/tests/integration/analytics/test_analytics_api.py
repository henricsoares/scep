from datetime import datetime
from uuid import UUID, uuid4

from app.infrastructure.database import Base, get_db
from app.modules.analytics.api.router import router as analytics_router
from app.modules.analytics.application.models import AnalyticsQuery, Granularity
from app.modules.analytics.application.service import (
    AnalyticsAuthorizationError,
    AnalyticsService,
    AnalyticsValidationError,
)
from app.modules.analytics.infrastructure.repository import AnalyticsRepository
from app.modules.charging.infrastructure.charging_session_model import ChargingSessionModel
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.charging.infrastructure.reservation_model import ReservationModel
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.telemetry.infrastructure import TelemetrySampleModel
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def user(role: HumanRole, facility_ids: list[UUID] | None = None) -> User:
    return User.create(
        email=f"{uuid4()}@example.com",
        display_name="Analytics User",
        password_hash="hash",
        account_type=AccountType.HUMAN,
        status=AccountStatus.ACTIVE,
        roles=[role],
        facility_ids=facility_ids or [],
    )


def database() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def seed(db: Session, *, activity: bool = True) -> tuple[FacilityModel, ChargingStationModel]:
    facility = FacilityModel(
        id=uuid4(),
        name=f"Facility {uuid4()}",
        facility_type="University",
        timezone="UTC",
        country="Brazil",
        city="Juiz de Fora",
        address="Campus",
        operating_hours=None,
        status="Active",
    )
    station = ChargingStationModel(
        id=uuid4(),
        facility_id=facility.id,
        name="Station",
        serial_number=str(uuid4()),
        maximum_power_kw=22,
        status="Available",
    )
    connector = ConnectorModel(
        id=uuid4(),
        charging_station_id=station.id,
        connector_type="Type2",
        maximum_power_kw=22,
        status="Available",
    )
    db.add_all([facility, station, connector])
    if activity:
        reservation_id, session_id = uuid4(), uuid4()
        db.add_all(
            [
                ReservationModel(
                    id=reservation_id,
                    owner_id=uuid4(),
                    vehicle_id=uuid4(),
                    connector_id=connector.id,
                    start_at=dt("2026-07-01T12:00Z"),
                    end_at=dt("2026-07-01T14:00Z"),
                    status="COMPLETED",
                ),
                ChargingSessionModel(
                    id=session_id,
                    reservation_id=reservation_id,
                    owner_id=uuid4(),
                    vehicle_id=uuid4(),
                    connector_id=connector.id,
                    status="COMPLETED",
                    started_at=dt("2026-07-01T12:10Z"),
                    ended_at=dt("2026-07-01T13:40Z"),
                ),
                TelemetrySampleModel(
                    id=uuid4(),
                    session_id=session_id,
                    sample_id="energy",
                    source="API_CLIENT",
                    recorded_at=dt("2026-07-01T13:00Z"),
                    received_at=dt("2026-07-01T13:00Z"),
                    energy_kwh=12.5,
                    created_at=dt("2026-07-01T13:00Z"),
                ),
            ]
        )
    db.commit()
    return facility, station


def query(facility: FacilityModel, granularity: Granularity | None = None) -> AnalyticsQuery:
    return AnalyticsQuery(
        dt("2026-07-01T00:00Z"),
        dt("2026-07-02T00:00Z"),
        facility_id=facility.id,
        granularity=granularity,
    )


def test_aggregate_series_and_openapi_contracts() -> None:
    with database() as db:
        facility, _ = seed(db)
        service = AnalyticsService(AnalyticsRepository(db))
        admin = user(HumanRole.PLATFORM_ADMINISTRATOR)
        overview = service.execute("overview", query(facility), admin)
        assert overview["reservations"]["fulfilled_reservations"] == 1
        assert overview["capacity"]["charging_duration_minutes"] == 90
        assert overview["energy"]["total_delivered_energy_kwh"] == 12.5
        for endpoint in ("reservations", "charging-sessions", "occupancy", "energy"):
            response = service.execute(endpoint, query(facility, Granularity.DAY), admin)
            assert len(response["series"]) == 1

    app = FastAPI()
    app.include_router(analytics_router)
    schema = app.openapi()
    assert "AnalyticsWindow" in schema["components"]["schemas"]
    assert schema["paths"]["/analytics/overview"]["get"]["security"] == [{"HTTPBearer": []}]
    schemas = schema["components"]["schemas"]
    assert any(name.startswith("SeriesItem_ReservationMetrics") for name in schemas)
    assert any(name.startswith("SeriesItem_EnergyMetrics") for name in schemas)


def test_time_series_uses_a_constant_number_of_database_queries() -> None:
    with database() as db:
        facility, _ = seed(db)
        engine = db.get_bind()
        assert isinstance(engine, Engine)
        selects = 0

        def count_selects(
            _connection: object,
            _cursor: object,
            statement: str,
            _parameters: object,
            _context: object,
            _executemany: bool,
        ) -> None:
            nonlocal selects
            if statement.lstrip().upper().startswith("SELECT"):
                selects += 1

        event.listen(engine, "before_cursor_execute", count_selects)
        service = AnalyticsService(AnalyticsRepository(db))
        daily = service.execute(
            "occupancy",
            query(facility, Granularity.DAY),
            user(HumanRole.PLATFORM_ADMINISTRATOR),
        )
        daily_selects = selects
        selects = 0
        hourly = service.execute(
            "occupancy",
            query(facility, Granularity.HOUR),
            user(HumanRole.PLATFORM_ADMINISTRATOR),
        )
        event.remove(engine, "before_cursor_execute", count_selects)

        assert len(daily["series"]) == 1
        assert len(hourly["series"]) == 24
        assert selects == daily_selects


def test_rest_endpoints_return_stable_aggregate_and_series_contracts() -> None:
    with database() as db:
        facility, _ = seed(db)
        app = FastAPI()
        app.include_router(analytics_router)
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[current_user] = lambda: user(HumanRole.PLATFORM_ADMINISTRATOR)
        client = TestClient(app)
        request_params = {
            "from": "2026-07-01T00:00:00Z",
            "to": "2026-07-02T00:00:00Z",
            "facility_id": str(facility.id),
        }
        try:
            overview = client.get("/analytics/overview", params=request_params)
            assert overview.status_code == 200
            assert "average_reservation_duration_minutes" not in overview.json()["reservations"]

            for endpoint in ("reservations", "charging-sessions", "occupancy", "energy"):
                aggregate = client.get(f"/analytics/{endpoint}", params=request_params)
                assert aggregate.status_code == 200
                assert "series" not in aggregate.json()

                series = client.get(
                    f"/analytics/{endpoint}",
                    params=request_params | {"granularity": "hour"},
                )
                assert series.status_code == 200
                assert len(series.json()["series"]) == 24

            invalid = client.get(
                "/analytics/overview",
                params=request_params | {"to": "2026-07-01T00:00:00Z"},
            )
            assert invalid.status_code == 400
        finally:
            client.close()


def test_empty_validation_and_authorization() -> None:
    with database() as db:
        facility, station = seed(db, activity=False)
        other, _ = seed(db, activity=False)
        service = AnalyticsService(AnalyticsRepository(db))
        operator = user(HumanRole.FACILITY_OPERATOR, [facility.id])
        empty = service.execute("reservations", query(facility), operator)
        assert empty["metrics"]["reservation_fulfillment_rate"] is None
        try:
            service.execute("overview", query(other), operator)
        except AnalyticsAuthorizationError:
            pass
        else:
            raise AssertionError("unauthorized Facility must be rejected")
        mismatch = AnalyticsQuery(
            dt("2026-07-01T00:00Z"),
            dt("2026-07-02T00:00Z"),
            facility_id=other.id,
            station_id=station.id,
        )
        try:
            service.execute("overview", mismatch, operator)
        except AnalyticsValidationError:
            pass
        else:
            raise AssertionError("mismatched hierarchy must be rejected")
