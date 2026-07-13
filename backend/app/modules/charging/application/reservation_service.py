import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import DBAPIError

from app.modules.charging.application.reservation_metrics import (
    reservation_conflicts_total,
    reservations_cancelled_total,
    reservations_created_total,
    reservations_no_show_total,
)
from app.modules.charging.domain.facility import FacilityStatus
from app.modules.charging.domain.reservation import Reservation, ReservationStatus
from app.modules.charging.domain.station import ChargingStationStatus, ConnectorStatus
from app.modules.charging.domain.vehicle import VehicleStatus
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.charging.infrastructure.reservation_repository import (
    SqlAlchemyReservationRepository,
    SqlAlchemyVehicleRepository,
)
from app.modules.charging.infrastructure.station_repository import (
    SqlAlchemyChargingStationRepository,
)
from app.modules.identity.application.authorization import is_admin
from app.modules.identity.domain.user import HumanRole, User
from app.shared.clock import Clock

logger = logging.getLogger(__name__)


class ReservationNotFoundError(Exception):
    pass


class SchedulingConflictError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ReservationService:
    def __init__(
        self,
        reservations: SqlAlchemyReservationRepository,
        vehicles: SqlAlchemyVehicleRepository,
        stations: SqlAlchemyChargingStationRepository,
        facilities: SqlAlchemyFacilityRepository,
        clock: Clock,
    ) -> None:
        self.reservations = reservations
        self.vehicles = vehicles
        self.stations = stations
        self.facilities = facilities
        self.clock = clock

    def reconcile_overdue(self) -> int:
        now = self.clock.now()
        count = 0
        for reservation in self.reservations.overdue_confirmed(now):
            self.reservations.update(reservation.mark_no_show(now=now))
            reservations_no_show_total.inc()
            count += 1
        if count:
            logger.info("reservation no-show reconciliation completed", extra={"count": count})
        return count

    def _vehicle_for_owner(self, vehicle_id: UUID, actor: User) -> tuple[UUID, object]:
        vehicle = self.vehicles.get(vehicle_id)
        if vehicle is None:
            raise ValueError("vehicle not found")
        if vehicle.status != VehicleStatus.ACTIVE:
            raise ValueError("vehicle must be ACTIVE")
        if vehicle.owner_id != actor.id and not is_admin(actor):
            raise ValueError("vehicle not found")
        return vehicle.owner_id, vehicle

    def _eligible_connector(self, connector_id: UUID) -> None:
        connector = self.stations.get_connector(connector_id)
        if connector is None:
            raise ValueError("connector not found")
        station = self.stations.get(connector.charging_station_id)
        if station is None:
            raise ValueError("charging station not found")
        facility = self.facilities.get(station.facility_id)
        if (
            facility is None
            or facility.status != FacilityStatus.ACTIVE
            or station.status != ChargingStationStatus.ACTIVE
            or connector.status == ConnectorStatus.OUT_OF_SERVICE
        ):
            raise ValueError("connector is not eligible for reservation")

    def _check_conflict(
        self,
        *,
        connector_id: UUID,
        vehicle_id: UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_id: UUID | None = None,
    ) -> None:
        conflict = self.reservations.find_conflict(
            connector_id=connector_id,
            vehicle_id=vehicle_id,
            start_at=start_at,
            end_at=end_at,
            exclude_id=exclude_id,
        )
        if conflict:
            reservation_conflicts_total.labels(
                "connector" if conflict.startswith("CONNECTOR") else "vehicle"
            ).inc()
            raise SchedulingConflictError(conflict)

    def _race_conflict(
        self,
        exc: DBAPIError,
        *,
        connector_id: UUID,
        vehicle_id: UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_id: UUID | None = None,
    ) -> SchedulingConflictError:
        text = str(exc.orig)
        code = self.reservations.find_conflict(
            connector_id=connector_id,
            vehicle_id=vehicle_id,
            start_at=start_at,
            end_at=end_at,
            exclude_id=exclude_id,
        )
        if code is None:
            code = (
                "VEHICLE_RESERVATION_CONFLICT"
                if "reservations_vehicle_no_overlap" in text
                else "CONNECTOR_RESERVATION_CONFLICT"
            )
        reservation_conflicts_total.labels(
            "vehicle" if code.startswith("VEHICLE") else "connector"
        ).inc()
        return SchedulingConflictError(code)

    def create(
        self,
        *,
        actor: User,
        vehicle_id: UUID,
        connector_id: UUID,
        start_at: datetime,
        end_at: datetime,
        owner_id: UUID | None = None,
    ) -> tuple[Reservation, bool]:
        self.reconcile_overdue()
        resolved_owner, _ = self._vehicle_for_owner(vehicle_id, actor)
        if owner_id is not None and owner_id != resolved_owner:
            raise ValueError("owner_id must match the Vehicle owner")
        self._eligible_connector(connector_id)
        reservation = Reservation.create(
            owner_id=resolved_owner,
            vehicle_id=vehicle_id,
            connector_id=connector_id,
            start_at=start_at,
            end_at=end_at,
            now=self.clock.now(),
        )
        self._check_conflict(
            connector_id=connector_id,
            vehicle_id=vehicle_id,
            start_at=reservation.start_at,
            end_at=reservation.end_at,
        )
        adjacent = self.reservations.has_adjacent(
            connector_id=connector_id,
            vehicle_id=vehicle_id,
            start_at=reservation.start_at,
            end_at=reservation.end_at,
        )
        try:
            saved = self.reservations.add(reservation)
        except DBAPIError as exc:
            raise self._race_conflict(
                exc,
                connector_id=reservation.connector_id,
                vehicle_id=reservation.vehicle_id,
                start_at=reservation.start_at,
                end_at=reservation.end_at,
            ) from exc
        reservations_created_total.inc()
        logger.info("reservation created", extra={"status": saved.status.value})
        return saved, adjacent

    def _can_view(self, actor: User, reservation: Reservation) -> bool:
        if is_admin(actor) or actor.id == reservation.owner_id:
            return True
        if HumanRole.RESEARCHER in actor.roles or HumanRole.DATA_SCIENTIST in actor.roles:
            return True
        if HumanRole.FACILITY_OPERATOR in actor.roles:
            connector = self.stations.get_connector(reservation.connector_id)
            station = (
                None if connector is None else self.stations.get(connector.charging_station_id)
            )
            return station is not None and station.facility_id in actor.facility_ids
        return False

    def get(self, reservation_id: UUID, *, actor: User) -> Reservation:
        self.reconcile_overdue()
        item = self.reservations.get(reservation_id)
        if item is None or not self._can_view(actor, item):
            raise ReservationNotFoundError("reservation not found")
        return item

    def list(
        self,
        *,
        actor: User,
        owner_id: UUID | None = None,
        facility_id: UUID | None = None,
        **filters: object,
    ) -> list[Reservation]:
        self.reconcile_overdue()
        facility_ids: tuple[UUID, ...] | None = None
        if not is_admin(actor):
            if HumanRole.FACILITY_OPERATOR in actor.roles:
                facility_ids = actor.facility_ids
                if facility_id is not None:
                    facility_ids = (facility_id,) if facility_id in actor.facility_ids else ()
            elif (
                HumanRole.RESEARCHER not in actor.roles
                and HumanRole.DATA_SCIENTIST not in actor.roles
            ):
                owner_id = actor.id
        elif facility_id is not None:
            facility_ids = (facility_id,)
        return self.reservations.list(
            owner_id=owner_id, facility_ids=facility_ids, **filters  # type: ignore[arg-type]
        )

    def reschedule(
        self,
        reservation_id: UUID,
        *,
        actor: User,
        vehicle_id: UUID | None,
        start_at: datetime | None,
        end_at: datetime | None,
    ) -> tuple[Reservation, bool]:
        item = self.get(reservation_id, actor=actor)
        if item.owner_id != actor.id and not is_admin(actor):
            raise PermissionError("reservation mutation is forbidden")
        target_vehicle_id = vehicle_id or item.vehicle_id
        owner_id, _ = self._vehicle_for_owner(target_vehicle_id, actor)
        if owner_id != item.owner_id:
            raise ValueError("Vehicle owner must match Reservation owner")
        self._eligible_connector(item.connector_id)
        updated = item.reschedule(
            vehicle_id=target_vehicle_id,
            start_at=start_at or item.start_at,
            end_at=end_at or item.end_at,
            now=self.clock.now(),
        )
        self._check_conflict(
            connector_id=updated.connector_id,
            vehicle_id=updated.vehicle_id,
            start_at=updated.start_at,
            end_at=updated.end_at,
            exclude_id=updated.id,
        )
        adjacent = self.reservations.has_adjacent(
            connector_id=updated.connector_id,
            vehicle_id=updated.vehicle_id,
            start_at=updated.start_at,
            end_at=updated.end_at,
            exclude_id=updated.id,
        )
        try:
            return self.reservations.update(updated), adjacent
        except DBAPIError as exc:
            raise self._race_conflict(
                exc,
                connector_id=updated.connector_id,
                vehicle_id=updated.vehicle_id,
                start_at=updated.start_at,
                end_at=updated.end_at,
                exclude_id=updated.id,
            ) from exc

    def cancel(self, reservation_id: UUID, *, actor: User) -> Reservation:
        item = self.get(reservation_id, actor=actor)
        if item.owner_id != actor.id and not is_admin(actor):
            raise PermissionError("reservation mutation is forbidden")
        updated = self.reservations.update(item.cancel(now=self.clock.now()))
        classification = "late" if updated.status == ReservationStatus.LATE_CANCELLED else "normal"
        reservations_cancelled_total.labels(classification).inc()
        logger.info("reservation cancelled", extra={"classification": classification})
        return updated
