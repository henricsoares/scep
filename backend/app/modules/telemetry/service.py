from __future__ import annotations

import logging
from datetime import datetime, timedelta
from uuid import UUID

from app.modules.charging.domain.charging_session import ChargingSessionStatus
from app.modules.charging.infrastructure.charging_session_repository import (
    SqlAlchemyChargingSessionRepository,
)
from app.modules.identity.application.authorization import is_admin
from app.modules.identity.domain.user import HumanRole, User
from app.modules.telemetry.domain import TelemetrySample
from app.modules.telemetry.infrastructure import (
    SqlAlchemyTelemetryRepository,
    TelemetryConflictError,
)
from app.modules.telemetry.metrics import (
    telemetry_batch_failures_total,
    telemetry_batch_ingestions_total,
    telemetry_duplicate_submissions_total,
    telemetry_samples_persisted_total,
    telemetry_samples_received_total,
    telemetry_validation_failures_total,
)

logger = logging.getLogger(__name__)


class TelemetryNotFoundError(Exception):
    pass


class TelemetryService:
    def __init__(
        self,
        telemetry: SqlAlchemyTelemetryRepository,
        sessions: SqlAlchemyChargingSessionRepository,
    ) -> None:
        self.telemetry = telemetry
        self.sessions = sessions

    def ingest(
        self, session_id: UUID, samples: list[TelemetrySample], *, actor: User, batch: bool
    ) -> tuple[list[TelemetrySample], bool]:
        telemetry_samples_received_total.inc(len(samples))
        if batch:
            telemetry_batch_ingestions_total.inc()
        try:
            session = self.sessions.get(session_id)
            if session is None or not (is_admin(actor) or session.owner_id == actor.id):
                logger.warning("telemetry ingestion denied", extra={"reason": "scope"})
                raise TelemetryNotFoundError("charging session not found")
            if session.status not in {
                ChargingSessionStatus.ACTIVE,
                ChargingSessionStatus.COMPLETED,
            }:
                raise ValueError("charging session is not eligible for telemetry")
            unique: dict[tuple[UUID, object, str], TelemetrySample] = {}
            for sample in samples:
                previous = unique.get(sample.idempotency_key)
                if previous is not None:
                    if not previous.same_producer_payload(sample):
                        raise TelemetryConflictError("conflicting duplicate in batch")
                    continue
                self._validate_time(session.started_at, session.ended_at, session.status, sample)
                unique[sample.idempotency_key] = sample
            canonical, new_count, duplicate_count = self.telemetry.ingest(list(unique.values()))
        except Exception as exc:
            if isinstance(exc, ValueError):
                telemetry_validation_failures_total.inc()
                logger.warning("telemetry validation failed", extra={"reason": "validation"})
            if batch:
                reason = "conflict" if isinstance(exc, TelemetryConflictError) else "validation"
                telemetry_batch_failures_total.labels(reason).inc()
            raise
        telemetry_samples_persisted_total.inc(new_count)
        telemetry_duplicate_submissions_total.inc(duplicate_count + len(samples) - len(unique))
        if duplicate_count or len(samples) != len(unique):
            logger.info(
                "telemetry duplicate accepted",
                extra={"operation": "batch" if batch else "single"},
            )
        logger.info(
            "telemetry ingestion completed",
            extra={"operation": "batch" if batch else "single", "persisted": new_count},
        )
        return canonical, new_count > 0

    def list(self, session_id: UUID, *, actor: User, **filters: object) -> list[TelemetrySample]:
        session = self.sessions.get(session_id)
        if session is None or not self._can_view(actor, session.owner_id, session.connector_id):
            logger.warning("telemetry listing denied", extra={"reason": "scope"})
            raise TelemetryNotFoundError("charging session not found")
        return self.telemetry.list(session_id, **filters)  # type: ignore[arg-type]

    def get(self, telemetry_id: UUID, *, actor: User) -> TelemetrySample:
        item = self.telemetry.get(telemetry_id)
        if item is None:
            raise TelemetryNotFoundError("telemetry sample not found")
        session = self.sessions.get(item.session_id)
        if session is None or not self._can_view(actor, session.owner_id, session.connector_id):
            logger.warning("telemetry retrieval denied", extra={"reason": "scope"})
            raise TelemetryNotFoundError("telemetry sample not found")
        return item

    def _can_view(self, actor: User, owner_id: UUID, connector_id: UUID) -> bool:
        return (
            is_admin(actor)
            or actor.id == owner_id
            or (
                HumanRole.FACILITY_OPERATOR in actor.roles
                and self.sessions.facility_id_for_connector(connector_id) in actor.facility_ids
            )
        )

    @staticmethod
    def _validate_time(
        started_at: datetime,
        ended_at: datetime | None,
        status: ChargingSessionStatus,
        sample: TelemetrySample,
    ) -> None:
        if sample.recorded_at < started_at:
            raise ValueError("recorded_at precedes charging session")
        upper = (
            sample.received_at + timedelta(minutes=5)
            if status == ChargingSessionStatus.ACTIVE
            else ended_at
        )
        if upper is None or sample.recorded_at > upper:
            raise ValueError("recorded_at is outside charging session interval")
