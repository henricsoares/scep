from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.health import router as health_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.observability import RequestCorrelationMiddleware, configure_tracing
from app.infrastructure.database import SessionLocal
from app.modules.charging.api.charging_sessions import router as charging_sessions_router
from app.modules.charging.api.facilities import router as facilities_router
from app.modules.charging.api.reservations import router as reservations_router
from app.modules.charging.api.stations import router as stations_router
from app.modules.charging.api.vehicles import router as vehicles_router
from app.modules.events.api import router as events_router
from app.modules.events.dispatcher import InternalEventDispatcher
from app.modules.events.infrastructure import configure_post_commit_dispatch
from app.modules.identity.api.auth import router as auth_router
from app.modules.identity.api.users import router as users_router
from app.modules.identity.application.user_service import UserService, bootstrap_admin
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from app.modules.telemetry.api import router as telemetry_router


def create_app(*, export_telemetry: bool | None = None) -> FastAPI:
    settings = get_settings()
    if export_telemetry is None:
        export_telemetry = not settings.otel_sdk_disabled
    endpoint = settings.otel_exporter_otlp_endpoint if export_telemetry else None
    configure_logging(settings.log_level, endpoint)
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    dispatcher = InternalEventDispatcher(SessionLocal)
    configure_post_commit_dispatch(dispatcher.recover)
    app.add_middleware(RequestCorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(users_router)
    with SessionLocal() as session:
        bootstrap_admin(
            UserService(SqlAlchemyUserRepository(session)),
            settings.bootstrap_admin_email,
            settings.bootstrap_admin_password,
            settings.bootstrap_admin_display_name,
        )
    app.include_router(facilities_router)
    app.include_router(stations_router)
    app.include_router(vehicles_router)
    app.include_router(reservations_router)
    app.include_router(charging_sessions_router)
    app.include_router(telemetry_router)
    app.include_router(events_router)

    @app.on_event("startup")
    def recover_domain_event_deliveries() -> None:
        dispatcher.recover()

    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    if endpoint:
        configure_tracing(app, endpoint)
    return app


app = create_app()
