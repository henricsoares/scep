from __future__ import annotations

import logging
from builtins import list as list_type
from uuid import UUID

from app.modules.charging.application.charging_session_metrics import (
    charging_session_conflicts_total,
    charging_session_failures_total,
    charging_sessions_activated_total,
    charging_sessions_completed_total,
)
from app.modules.charging.application.reservation_service import (
    ReservationNotFoundError,
    ReservationService,
)
from app.modules.charging.application.station_service import ConnectorNotFoundError
from app.modules.charging.application.vehicle_service import VehicleNotFoundError
from app.modules.charging.domain.charging_session import ChargingSession
from app.modules.charging.infrastructure.charging_session_repository import (
    ChargingSessionWriteConflict,
    SqlAlchemyChargingSessionRepository,
)
from app.modules.charging.infrastructure.reservation_repository import SqlAlchemyVehicleRepository
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from app.modules.identity.application.authorization import is_admin
from app.modules.identity.domain.user import HumanRole, User
from app.shared.clock import Clock

logger = logging.getLogger(__name__)


class ChargingSessionNotFoundError(Exception):
    pass


class ChargingSessionConflictError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ChargingSessionService:
    def __init__(
        self,
        sessions: SqlAlchemyChargingSessionRepository,
        reservations: ReservationService,
        vehicles: SqlAlchemyVehicleRepository,
        stations: SqlAlchemyChargingStationRepository,
        clock: Clock,
    ) -> None:
        self.sessions = sessions
        self.reservations = reservations
        self.vehicles = vehicles
        self.stations = stations
        self.clock = clock

    def activate(self, reservation_id: UUID, *, actor: User) -> ChargingSession:
        try:
            reservation = self.reservations.get(reservation_id, actor=actor)
            if reservation.owner_id != actor.id and not is_admin(actor):
                logger.warning("charging session activation denied", extra={"reason": "scope"})
                raise PermissionError("reservation activation is forbidden")
            item = self.sessions.activate(reservation_id, now=self.clock.now())
        except ChargingSessionWriteConflict as exc:
            resource = (
                "vehicle"
                if exc.code.startswith("VEHICLE")
                else "connector" if exc.code.startswith("CONNECTOR") else "reservation"
            )
            charging_session_conflicts_total.labels(resource).inc()
            logger.warning("charging session activation conflict", extra={"reason": resource})
            raise ChargingSessionConflictError(exc.code) from exc
        except Exception as exc:
            charging_session_failures_total.labels("activation", self._reason(exc)).inc()
            raise
        charging_sessions_activated_total.inc()
        logger.info("charging session activated", extra={"status": item.status.value})
        return item

    def complete(self, session_id: UUID, *, actor: User) -> ChargingSession:
        try:
            item = self.get(session_id, actor=actor)
            permitted = item.owner_id == actor.id or is_admin(actor)
            if not permitted and HumanRole.FACILITY_OPERATOR in actor.roles:
                permitted = (
                    self.sessions.facility_id_for_connector(item.connector_id) in actor.facility_ids
                )
            if not permitted:
                logger.warning("charging session completion denied", extra={"reason": "scope"})
                raise PermissionError("charging session completion is forbidden")
            completed, connector_status = self.sessions.complete(session_id, now=self.clock.now())
        except Exception as exc:
            charging_session_failures_total.labels("completion", self._reason(exc)).inc()
            raise
        charging_sessions_completed_total.inc()
        logger.info(
            "charging session completed",
            extra={"status": completed.status.value, "connector_status": connector_status.value},
        )
        return completed

    def _can_view(self, actor: User, item: ChargingSession) -> bool:
        if is_admin(actor) or item.owner_id == actor.id:
            return True
        return (
            HumanRole.FACILITY_OPERATOR in actor.roles
            and self.sessions.facility_id_for_connector(item.connector_id) in actor.facility_ids
        )

    def get(self, session_id: UUID, *, actor: User) -> ChargingSession:
        item = self.sessions.get(session_id)
        if item is None or not self._can_view(actor, item):
            raise ChargingSessionNotFoundError("charging session not found")
        return item

    def list(
        self,
        *,
        actor: User,
        owner_id: UUID | None = None,
        facility_id: UUID | None = None,
        **filters: object,
    ) -> list_type[ChargingSession]:
        facility_ids: tuple[UUID, ...] | None = None
        visibility_owner_id: UUID | None = None
        if not is_admin(actor):
            if HumanRole.FACILITY_OPERATOR in actor.roles:
                facility_ids = actor.facility_ids
                visibility_owner_id = actor.id
            else:
                owner_id = actor.id
        return self.sessions.list(
            owner_id=owner_id,
            facility_ids=facility_ids,
            visibility_owner_id=visibility_owner_id,
            facility_id=facility_id,
            **filters,  # type: ignore[arg-type]
        )

    def list_for_connector(
        self, connector_id: UUID, *, actor: User, **filters: object
    ) -> list_type[ChargingSession]:
        if self.stations.get_connector(connector_id) is None:
            raise ConnectorNotFoundError("connector not found")
        return self.list(actor=actor, connector_id=connector_id, **filters)  # type: ignore[arg-type]

    def list_for_vehicle(
        self, vehicle_id: UUID, *, actor: User, **filters: object
    ) -> list_type[ChargingSession]:
        vehicle = self.vehicles.get(vehicle_id)
        if vehicle is None:
            raise VehicleNotFoundError("vehicle not found")
        if (
            vehicle.owner_id != actor.id
            and not is_admin(actor)
            and HumanRole.FACILITY_OPERATOR not in actor.roles
        ):
            raise VehicleNotFoundError("vehicle not found")
        return self.list(actor=actor, vehicle_id=vehicle_id, **filters)  # type: ignore[arg-type]

    @staticmethod
    def _reason(exc: Exception) -> str:
        if isinstance(exc, PermissionError):
            return "authorization"
        if isinstance(exc, (ReservationNotFoundError, ChargingSessionNotFoundError)):
            return "not_found"
        if isinstance(exc, ChargingSessionWriteConflict):
            return "conflict"
        return "validation"
