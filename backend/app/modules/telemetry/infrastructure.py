from __future__ import annotations

import hashlib
from builtins import list as list_type
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, String, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.infrastructure.database import Base
from app.modules.telemetry.domain import TelemetrySample, TelemetrySource


class TelemetrySampleModel(Base):
    __tablename__ = "telemetry_samples"
    __table_args__ = (
        CheckConstraint("source IN ('SIMULATOR', 'API_CLIENT')", name="ck_telemetry_source"),
        CheckConstraint("power_kw IS NULL OR power_kw >= 0", name="ck_telemetry_power"),
        CheckConstraint("energy_kwh IS NULL OR energy_kwh >= 0", name="ck_telemetry_energy"),
        CheckConstraint(
            "state_of_charge_percent IS NULL OR "
            "(state_of_charge_percent >= 0 AND state_of_charge_percent <= 100)",
            name="ck_telemetry_soc",
        ),
        CheckConstraint(
            "power_kw IS NOT NULL OR energy_kwh IS NOT NULL OR "
            "state_of_charge_percent IS NOT NULL",
            name="ck_telemetry_measurement_present",
        ),
        CheckConstraint(
            "(power_kw IS NULL OR power_kw NOT IN ('Infinity', '-Infinity', 'NaN')) AND "
            "(energy_kwh IS NULL OR energy_kwh NOT IN ('Infinity', '-Infinity', 'NaN')) AND "
            "(state_of_charge_percent IS NULL OR "
            "state_of_charge_percent NOT IN ('Infinity', '-Infinity', 'NaN'))",
            name="ck_telemetry_finite",
        ),
        Index(
            "uq_telemetry_session_source_sample",
            "session_id",
            "source",
            "sample_id",
            unique=True,
        ),
        Index("ix_telemetry_session_recorded", "session_id", "recorded_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("charging_sessions.id", ondelete="RESTRICT"), nullable=False
    )
    sample_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    power_kw: Mapped[float | None] = mapped_column(Float)
    energy_kwh: Mapped[float | None] = mapped_column(Float)
    state_of_charge_percent: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TelemetryConflictError(Exception):
    pass


class SqlAlchemyTelemetryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, telemetry_id: UUID) -> TelemetrySample | None:
        model = self.session.get(TelemetrySampleModel, telemetry_id)
        return None if model is None else self._domain(model)

    def list(
        self,
        session_id: UUID,
        *,
        recorded_from: datetime | None = None,
        recorded_to: datetime | None = None,
        source: TelemetrySource | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list_type[TelemetrySample]:
        stmt = select(TelemetrySampleModel).where(TelemetrySampleModel.session_id == session_id)
        if recorded_from is not None:
            stmt = stmt.where(TelemetrySampleModel.recorded_at >= recorded_from)
        if recorded_to is not None:
            stmt = stmt.where(TelemetrySampleModel.recorded_at <= recorded_to)
        if source is not None:
            stmt = stmt.where(TelemetrySampleModel.source == source.value)
        stmt = stmt.order_by(TelemetrySampleModel.recorded_at, TelemetrySampleModel.id)
        result = self.session.scalars(stmt.offset(offset).limit(limit))
        return [self._domain(item) for item in result]

    def ingest(
        self, samples: list_type[TelemetrySample]
    ) -> tuple[list_type[TelemetrySample], int, int]:
        try:
            self._lock_keys(samples)
            canonical: list_type[TelemetrySample] = []
            new_count = 0
            duplicate_count = 0
            for sample in samples:
                existing_model = self.session.scalar(
                    select(TelemetrySampleModel).where(
                        TelemetrySampleModel.session_id == sample.session_id,
                        TelemetrySampleModel.source == sample.source.value,
                        TelemetrySampleModel.sample_id == sample.sample_id,
                    )
                )
                if existing_model is not None:
                    existing = self._domain(existing_model)
                    if not existing.same_producer_payload(sample):
                        raise TelemetryConflictError("idempotency key has conflicting payload")
                    canonical.append(existing)
                    duplicate_count += 1
                    continue
                self.session.add(self._model(sample))
                self.session.flush()
                canonical.append(sample)
                new_count += 1
            self.session.commit()
            return canonical, new_count, duplicate_count
        except TelemetryConflictError:
            self.session.rollback()
            raise
        except IntegrityError as exc:
            self.session.rollback()
            raise TelemetryConflictError("concurrent idempotency conflict") from exc
        except Exception:
            self.session.rollback()
            raise

    def _lock_keys(self, samples: list_type[TelemetrySample]) -> None:
        if self.session.get_bind().dialect.name != "postgresql":
            return
        values = set()
        for item in samples:
            raw = f"{item.session_id}:{item.source.value}:{item.sample_id}".encode()
            values.add(int.from_bytes(hashlib.sha256(raw).digest()[:8], "big", signed=True))
        for value in sorted(values):
            self.session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": value})

    @staticmethod
    def _model(item: TelemetrySample) -> TelemetrySampleModel:
        return TelemetrySampleModel(**item.__dict__ | {"source": item.source.value})

    @staticmethod
    def _domain(model: TelemetrySampleModel) -> TelemetrySample:
        def utc(value: datetime) -> datetime:
            return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

        return TelemetrySample(
            id=model.id,
            session_id=model.session_id,
            sample_id=model.sample_id,
            source=TelemetrySource(model.source),
            recorded_at=utc(model.recorded_at),
            received_at=utc(model.received_at),
            power_kw=model.power_kw,
            energy_kwh=model.energy_kwh,
            state_of_charge_percent=model.state_of_charge_percent,
            created_at=utc(model.created_at),
        )
