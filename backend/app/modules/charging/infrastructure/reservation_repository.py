from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.modules.charging.domain.reservation import (
    BLOCKING_STATUSES,
    Reservation,
    ReservationStatus,
)
from app.modules.charging.domain.vehicle import Vehicle, VehicleStatus
from app.modules.charging.infrastructure.persistence_errors import (
    classify_reservation_calendar_write,
)
from app.modules.charging.infrastructure.reservation_model import ReservationModel, VehicleModel


class SqlAlchemyVehicleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, vehicle: Vehicle) -> Vehicle:
        self.session.add(self._model(vehicle))
        try:
            self.session.commit()
        except DBAPIError:
            self.session.rollback()
            raise
        return self.get(vehicle.id) or vehicle

    def get(self, vehicle_id: UUID) -> Vehicle | None:
        model = self.session.get(VehicleModel, vehicle_id)
        return None if model is None else self._domain(model)

    def list(
        self, *, owner_id: UUID | None, status: VehicleStatus | None, offset: int, limit: int
    ) -> list[Vehicle]:
        stmt = select(VehicleModel)
        if owner_id is not None:
            stmt = stmt.where(VehicleModel.owner_id == owner_id)
        if status is not None:
            stmt = stmt.where(VehicleModel.status == status.value)
        stmt = stmt.order_by(VehicleModel.created_at, VehicleModel.id).offset(offset).limit(limit)
        return [self._domain(item) for item in self.session.scalars(stmt).all()]

    def update(self, vehicle: Vehicle) -> Vehicle:
        model = self.session.get(VehicleModel, vehicle.id)
        if model is None:
            raise ValueError("vehicle not found")
        model.display_name = vehicle.display_name
        model.status = vehicle.status.value
        model.updated_at = vehicle.updated_at
        try:
            self.session.commit()
        except DBAPIError:
            self.session.rollback()
            raise
        return self.get(vehicle.id) or vehicle

    @staticmethod
    def _model(vehicle: Vehicle) -> VehicleModel:
        return VehicleModel(**vehicle.__dict__ | {"status": vehicle.status.value})

    @staticmethod
    def _domain(model: VehicleModel) -> Vehicle:
        return Vehicle(
            model.id,
            model.owner_id,
            model.display_name,
            VehicleStatus(model.status),
            _utc(model.created_at),
            _utc(model.updated_at),
        )


class SqlAlchemyReservationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, reservation: Reservation) -> Reservation:
        self.session.add(self._model(reservation))
        try:
            self.session.commit()
        except DBAPIError as exc:
            self.session.rollback()
            conflict = classify_reservation_calendar_write(exc)
            if conflict is not None:
                raise conflict from exc
            raise
        return self.get(reservation.id) or reservation

    def get(self, reservation_id: UUID) -> Reservation | None:
        model = self.session.get(ReservationModel, reservation_id)
        return None if model is None else self._domain(model)

    def list(
        self,
        *,
        owner_id: UUID | None = None,
        vehicle_id: UUID | None = None,
        connector_id: UUID | None = None,
        status: ReservationStatus | None = None,
        facility_ids: tuple[UUID, ...] | None = None,
        visibility_owner_id: UUID | None = None,
        facility_id: UUID | None = None,
        station_id: UUID | None = None,
        starts_before: datetime | None = None,
        ends_after: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Reservation]:
        stmt = select(ReservationModel)
        if owner_id is not None:
            stmt = stmt.where(ReservationModel.owner_id == owner_id)
        if vehicle_id is not None:
            stmt = stmt.where(ReservationModel.vehicle_id == vehicle_id)
        if connector_id is not None:
            stmt = stmt.where(ReservationModel.connector_id == connector_id)
        if status is not None:
            stmt = stmt.where(ReservationModel.status == status.value)
        if starts_before is not None:
            stmt = stmt.where(ReservationModel.start_at < starts_before)
        if ends_after is not None:
            stmt = stmt.where(ReservationModel.end_at > ends_after)
        if station_id is not None or facility_id is not None or facility_ids is not None:
            from app.modules.charging.infrastructure.station_model import (
                ChargingStationModel,
                ConnectorModel,
            )

            stmt = stmt.join(ConnectorModel, ConnectorModel.id == ReservationModel.connector_id)
            stmt = stmt.join(
                ChargingStationModel,
                ChargingStationModel.id == ConnectorModel.charging_station_id,
            )
            if station_id is not None:
                stmt = stmt.where(ChargingStationModel.id == station_id)
            if facility_id is not None:
                stmt = stmt.where(ChargingStationModel.facility_id == facility_id)
            if facility_ids is not None:
                facility_scope = ChargingStationModel.facility_id.in_(facility_ids)
                if visibility_owner_id is not None:
                    stmt = stmt.where(
                        or_(
                            ReservationModel.owner_id == visibility_owner_id,
                            facility_scope,
                        )
                    )
                else:
                    stmt = stmt.where(facility_scope)
        elif visibility_owner_id is not None:
            stmt = stmt.where(ReservationModel.owner_id == visibility_owner_id)
        stmt = (
            stmt.order_by(ReservationModel.start_at, ReservationModel.id)
            .offset(offset)
            .limit(limit)
        )
        return [self._domain(item) for item in self.session.scalars(stmt).all()]

    def find_conflict(
        self,
        *,
        connector_id: UUID,
        vehicle_id: UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_id: UUID | None = None,
    ) -> str | None:
        self._lock_calendars(connector_id, vehicle_id)
        base = and_(
            ReservationModel.status.in_([status.value for status in BLOCKING_STATUSES]),
            ReservationModel.start_at < end_at,
            start_at < ReservationModel.end_at,
        )
        if exclude_id is not None:
            base = and_(base, ReservationModel.id != exclude_id)
        connector = self.session.scalar(
            select(ReservationModel.id)
            .where(base, ReservationModel.connector_id == connector_id)
            .limit(1)
        )
        if connector is not None:
            return "CONNECTOR_RESERVATION_CONFLICT"
        vehicle = self.session.scalar(
            select(ReservationModel.id)
            .where(base, ReservationModel.vehicle_id == vehicle_id)
            .limit(1)
        )
        return "VEHICLE_RESERVATION_CONFLICT" if vehicle is not None else None

    def _lock_calendars(self, connector_id: UUID, vehicle_id: UUID) -> None:
        bind = self.session.get_bind()
        if bind.dialect.name != "postgresql":
            return
        # Lock both calendar keys in a stable order. This serializes the application-level
        # check-and-write path, while exclusion constraints remain the final database guard.
        keys = sorted({connector_id.int & ((1 << 63) - 1), vehicle_id.int & ((1 << 63) - 1)})
        for key in keys:
            self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

    def has_adjacent(
        self,
        *,
        connector_id: UUID,
        vehicle_id: UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_id: UUID | None = None,
    ) -> bool:
        stmt = select(ReservationModel.id).where(
            ReservationModel.status.in_([status.value for status in BLOCKING_STATUSES]),
            or_(
                ReservationModel.connector_id == connector_id,
                ReservationModel.vehicle_id == vehicle_id,
            ),
            or_(ReservationModel.end_at == start_at, ReservationModel.start_at == end_at),
        )
        if exclude_id is not None:
            stmt = stmt.where(ReservationModel.id != exclude_id)
        return self.session.scalar(stmt.limit(1)) is not None

    def reconcile_overdue(self, now: datetime) -> int:
        stmt = (
            update(ReservationModel)
            .where(
                ReservationModel.status == ReservationStatus.CONFIRMED.value,
                ReservationModel.start_at < now - timedelta(minutes=15),
            )
            .values(
                status=ReservationStatus.NO_SHOW.value,
                no_show_at=now,
                updated_at=now,
            )
            .returning(ReservationModel.id)
        )
        try:
            transitioned = tuple(self.session.scalars(stmt).all())
            self.session.commit()
        except DBAPIError:
            self.session.rollback()
            raise
        return len(transitioned)

    def update(self, reservation: Reservation) -> Reservation:
        model = self.session.get(ReservationModel, reservation.id)
        if model is None:
            raise ValueError("reservation not found")
        for name in (
            "vehicle_id",
            "start_at",
            "end_at",
            "activated_at",
            "completed_at",
            "cancelled_at",
            "late_cancelled_at",
            "no_show_at",
            "updated_at",
        ):
            setattr(model, name, getattr(reservation, name))
        model.status = reservation.status.value
        try:
            self.session.commit()
        except DBAPIError as exc:
            self.session.rollback()
            conflict = classify_reservation_calendar_write(exc)
            if conflict is not None:
                raise conflict from exc
            raise
        return self.get(reservation.id) or reservation

    @staticmethod
    def _model(item: Reservation) -> ReservationModel:
        return ReservationModel(**item.__dict__ | {"status": item.status.value})

    @staticmethod
    def _domain(model: ReservationModel) -> Reservation:
        return Reservation(
            id=model.id,
            owner_id=model.owner_id,
            vehicle_id=model.vehicle_id,
            connector_id=model.connector_id,
            start_at=_utc(model.start_at),
            end_at=_utc(model.end_at),
            status=ReservationStatus(model.status),
            created_at=_utc(model.created_at),
            updated_at=_utc(model.updated_at),
            activated_at=_utc_or_none(model.activated_at),
            completed_at=_utc_or_none(model.completed_at),
            cancelled_at=_utc_or_none(model.cancelled_at),
            late_cancelled_at=_utc_or_none(model.late_cancelled_at),
            no_show_at=_utc_or_none(model.no_show_at),
        )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _utc_or_none(value: datetime | None) -> datetime | None:
    return None if value is None else _utc(value)
