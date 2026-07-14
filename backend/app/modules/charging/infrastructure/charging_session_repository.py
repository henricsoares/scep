from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.charging.domain.charging_session import (
    ChargingSession,
    ChargingSessionStatus,
)
from app.modules.charging.domain.facility import FacilityStatus
from app.modules.charging.domain.reservation import Reservation, ReservationStatus
from app.modules.charging.domain.station import ChargingStationStatus, ConnectorStatus
from app.modules.charging.infrastructure.charging_session_model import ChargingSessionModel
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.charging.infrastructure.reservation_model import ReservationModel
from app.modules.charging.infrastructure.station_model import ChargingStationModel, ConnectorModel


class ChargingSessionWriteConflict(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


CONSTRAINT_CODES = {
    "uq_charging_sessions_reservation": "RESERVATION_SESSION_CONFLICT",
    "uq_charging_sessions_active_vehicle": "VEHICLE_ACTIVE_SESSION_CONFLICT",
    "uq_charging_sessions_active_connector": "CONNECTOR_ACTIVE_SESSION_CONFLICT",
}


class SqlAlchemyChargingSessionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, session_id: UUID) -> ChargingSession | None:
        model = self.session.get(ChargingSessionModel, session_id)
        return None if model is None else self._domain(model)

    def list(
        self,
        *,
        owner_id: UUID | None = None,
        vehicle_id: UUID | None = None,
        connector_id: UUID | None = None,
        status: ChargingSessionStatus | None = None,
        facility_ids: tuple[UUID, ...] | None = None,
        visibility_owner_id: UUID | None = None,
        facility_id: UUID | None = None,
        station_id: UUID | None = None,
        started_after: datetime | None = None,
        started_before: datetime | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ChargingSession]:
        stmt = select(ChargingSessionModel)
        if owner_id is not None:
            stmt = stmt.where(ChargingSessionModel.owner_id == owner_id)
        if vehicle_id is not None:
            stmt = stmt.where(ChargingSessionModel.vehicle_id == vehicle_id)
        if connector_id is not None:
            stmt = stmt.where(ChargingSessionModel.connector_id == connector_id)
        if status is not None:
            stmt = stmt.where(ChargingSessionModel.status == status.value)
        if started_after is not None:
            stmt = stmt.where(ChargingSessionModel.started_at >= started_after)
        if started_before is not None:
            stmt = stmt.where(ChargingSessionModel.started_at <= started_before)
        if station_id is not None or facility_id is not None or facility_ids is not None:
            stmt = stmt.join(
                ConnectorModel, ConnectorModel.id == ChargingSessionModel.connector_id
            ).join(
                ChargingStationModel,
                ChargingStationModel.id == ConnectorModel.charging_station_id,
            )
            if station_id is not None:
                stmt = stmt.where(ChargingStationModel.id == station_id)
            if facility_id is not None:
                stmt = stmt.where(ChargingStationModel.facility_id == facility_id)
            if facility_ids is not None:
                scope = ChargingStationModel.facility_id.in_(facility_ids)
                stmt = stmt.where(
                    or_(ChargingSessionModel.owner_id == visibility_owner_id, scope)
                    if visibility_owner_id is not None
                    else scope
                )
        elif visibility_owner_id is not None:
            stmt = stmt.where(ChargingSessionModel.owner_id == visibility_owner_id)
        stmt = (
            stmt.order_by(ChargingSessionModel.started_at, ChargingSessionModel.id)
            .offset(offset)
            .limit(limit)
        )
        return [self._domain(model) for model in self.session.scalars(stmt).all()]

    def activate(self, reservation_id: UUID, *, now: datetime) -> ChargingSession:
        try:
            reservation_model = self.session.scalar(
                select(ReservationModel)
                .where(ReservationModel.id == reservation_id)
                .with_for_update()
            )
            if reservation_model is None:
                raise ValueError("reservation not found")
            self._lock_keys(reservation_model.vehicle_id, reservation_model.connector_id)
            existing = self.session.scalar(
                select(ChargingSessionModel.id).where(
                    ChargingSessionModel.reservation_id == reservation_id
                )
            )
            if existing is not None:
                raise ChargingSessionWriteConflict("RESERVATION_SESSION_CONFLICT")
            connector = self.session.scalar(
                select(ConnectorModel)
                .where(ConnectorModel.id == reservation_model.connector_id)
                .with_for_update()
            )
            if connector is None:
                raise ValueError("connector not found")
            station = self.session.get(ChargingStationModel, connector.charging_station_id)
            facility = (
                None if station is None else self.session.get(FacilityModel, station.facility_id)
            )
            infrastructure_ok = (
                station is not None
                and facility is not None
                and station.status == ChargingStationStatus.ACTIVE.value
                and facility.status == FacilityStatus.ACTIVE.value
                and connector.status
                in {ConnectorStatus.AVAILABLE.value, ConnectorStatus.RESERVED.value}
            )
            reservation = self._reservation_domain(reservation_model)
            activated = reservation.activate(
                now=now,
                connector_operational=infrastructure_ok,
                connector_available=infrastructure_ok,
                active_session_exists=False,
            )
            item = ChargingSession.activate(
                reservation_id=reservation.id,
                owner_id=reservation.owner_id,
                vehicle_id=reservation.vehicle_id,
                connector_id=reservation.connector_id,
                now=now,
            )
            self.session.add(self._model(item))
            reservation_model.status = activated.status.value
            reservation_model.activated_at = activated.activated_at
            reservation_model.updated_at = activated.updated_at
            connector.status = ConnectorStatus.CHARGING.value
            connector.updated_at = now
            self.session.commit()
            return self.get(item.id) or item
        except ChargingSessionWriteConflict:
            self.session.rollback()
            raise
        except IntegrityError as exc:
            self.session.rollback()
            diagnostic = getattr(exc.orig, "diag", None)
            name = getattr(diagnostic, "constraint_name", None)
            name = name if isinstance(name, str) else ""
            code = CONSTRAINT_CODES.get(name, "CHARGING_SESSION_CONFLICT")
            raise ChargingSessionWriteConflict(code) from exc
        except Exception:
            self.session.rollback()
            raise

    def complete(
        self, session_id: UUID, *, now: datetime
    ) -> tuple[ChargingSession, ConnectorStatus]:
        try:
            model = self.session.scalar(
                select(ChargingSessionModel)
                .where(ChargingSessionModel.id == session_id)
                .with_for_update()
            )
            if model is None:
                raise ValueError("charging session not found")
            item = self._domain(model)
            completed = item.complete(now=now)
            reservation = self.session.scalar(
                select(ReservationModel)
                .where(ReservationModel.id == item.reservation_id)
                .with_for_update()
            )
            connector = self.session.scalar(
                select(ConnectorModel)
                .where(ConnectorModel.id == item.connector_id)
                .with_for_update()
            )
            if reservation is None or connector is None:
                raise ValueError("charging session infrastructure is incomplete")
            reservation_domain = self._reservation_domain(reservation).complete(now=now)
            model.status = completed.status.value
            model.ended_at = completed.ended_at
            model.updated_at = completed.updated_at
            reservation.status = reservation_domain.status.value
            reservation.completed_at = reservation_domain.completed_at
            reservation.updated_at = reservation_domain.updated_at
            next_status = self._restored_connector_status(item, connector, now)
            connector.status = next_status.value
            connector.updated_at = now
            self.session.commit()
            return self.get(item.id) or completed, next_status
        except Exception:
            self.session.rollback()
            raise

    def facility_id_for_connector(self, connector_id: UUID) -> UUID | None:
        return self.session.scalar(
            select(ChargingStationModel.facility_id)
            .join(ConnectorModel, ConnectorModel.charging_station_id == ChargingStationModel.id)
            .where(ConnectorModel.id == connector_id)
        )

    def _restored_connector_status(
        self, item: ChargingSession, connector: ConnectorModel, now: datetime
    ) -> ConnectorStatus:
        station = self.session.get(ChargingStationModel, connector.charging_station_id)
        facility = None if station is None else self.session.get(FacilityModel, station.facility_id)
        if (
            station is None
            or facility is None
            or station.status != ChargingStationStatus.ACTIVE.value
            or facility.status != FacilityStatus.ACTIVE.value
        ):
            return ConnectorStatus.OUT_OF_SERVICE
        reserved = self.session.scalar(
            select(ReservationModel.id)
            .where(
                ReservationModel.id != item.reservation_id,
                ReservationModel.connector_id == item.connector_id,
                ReservationModel.status == ReservationStatus.CONFIRMED.value,
                ReservationModel.start_at <= now,
                ReservationModel.end_at > now,
            )
            .limit(1)
        )
        return ConnectorStatus.RESERVED if reserved is not None else ConnectorStatus.AVAILABLE

    def _lock_keys(self, vehicle_id: UUID, connector_id: UUID) -> None:
        if self.session.get_bind().dialect.name != "postgresql":
            return
        for key in sorted({vehicle_id.int & ((1 << 63) - 1), connector_id.int & ((1 << 63) - 1)}):
            self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": key})

    @staticmethod
    def _model(item: ChargingSession) -> ChargingSessionModel:
        return ChargingSessionModel(**item.__dict__ | {"status": item.status.value})

    @staticmethod
    def _domain(model: ChargingSessionModel) -> ChargingSession:
        return ChargingSession(
            id=model.id,
            reservation_id=model.reservation_id,
            owner_id=model.owner_id,
            vehicle_id=model.vehicle_id,
            connector_id=model.connector_id,
            status=ChargingSessionStatus(model.status),
            started_at=_utc(model.started_at),
            ended_at=None if model.ended_at is None else _utc(model.ended_at),
            created_at=_utc(model.created_at),
            updated_at=_utc(model.updated_at),
        )

    @staticmethod
    def _reservation_domain(model: ReservationModel) -> Reservation:
        def optional(value: datetime | None) -> datetime | None:
            return None if value is None else _utc(value)

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
            activated_at=optional(model.activated_at),
            completed_at=optional(model.completed_at),
            cancelled_at=optional(model.cancelled_at),
            late_cancelled_at=optional(model.late_cancelled_at),
            no_show_at=optional(model.no_show_at),
        )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
