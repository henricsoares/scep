from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship, selectinload

from app.infrastructure.database import Base
from app.modules.simulation.domain import SimulationRun, SimulationRunStatus


class SimulationRunFacilityModel(Base):
    __tablename__ = "simulation_run_facilities"

    simulation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), primary_key=True
    )
    facility_id: Mapped[UUID] = mapped_column(
        ForeignKey("facilities.id", ondelete="RESTRICT"), primary_key=True
    )


class SimulationRunEvDriverModel(Base):
    __tablename__ = "simulation_run_evdrivers"

    simulation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )


class SimulationRunModel(Base):
    __tablename__ = "simulation_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('DRAFT','RUNNING','COMPLETED','CANCELLED')",
            name="ck_simulation_runs_status",
        ),
        CheckConstraint(
            "logical_start_at < logical_end_at", name="ck_simulation_runs_logical_window"
        ),
        CheckConstraint(
            "last_accepted_simulated_at IS NULL OR "
            "(last_accepted_simulated_at >= logical_start_at AND "
            "last_accepted_simulated_at <= logical_end_at)",
            name="ck_simulation_runs_last_accepted_window",
        ),
        CheckConstraint(
            "scenario_sha256 IS NULL OR "
            "(length(scenario_sha256) = 64 AND scenario_sha256 = lower(scenario_sha256))",
            name="ck_simulation_runs_scenario_sha256",
        ),
        Index("ix_simulation_runs_status_created", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    logical_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    logical_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_accepted_simulated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    credential_hash: Mapped[str | None] = mapped_column(String(255))
    external_scenario_id: Mapped[str | None] = mapped_column(String(255))
    external_scenario_version: Mapped[str | None] = mapped_column(String(128))
    scenario_sha256: Mapped[str | None] = mapped_column(String(64))
    simulator_version: Mapped[str | None] = mapped_column(String(128))
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    facilities: Mapped[list[SimulationRunFacilityModel]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )
    evdrivers: Mapped[list[SimulationRunEvDriverModel]] = relationship(
        lazy="selectin", cascade="all, delete-orphan"
    )


class SimulationEventReceiptModel(Base):
    __tablename__ = "simulation_event_receipts"
    __table_args__ = (
        UniqueConstraint(
            "simulation_run_id",
            "operation",
            "simulation_event_id",
            name="uq_simulation_event_receipts_logical_key",
        ),
        CheckConstraint(
            "response_status >= 200 AND response_status < 300", name="ck_receipt_status"
        ),
        CheckConstraint("length(request_sha256) = 64", name="ck_receipt_request_sha256"),
        Index("ix_simulation_event_receipts_run_time", "simulation_run_id", "simulated_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    simulation_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("simulation_runs.id", ondelete="RESTRICT"), nullable=False
    )
    simulation_event_id: Mapped[UUID] = mapped_column(nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    simulated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[UUID | None]
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SimulationRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, item: SimulationRun) -> SimulationRun:
        self.session.add(self._model(item))
        self._commit()
        return self.get(item.id) or item

    def get(self, run_id: UUID, *, for_update: bool = False) -> SimulationRun | None:
        stmt = (
            select(SimulationRunModel)
            .options(
                selectinload(SimulationRunModel.facilities),
                selectinload(SimulationRunModel.evdrivers),
            )
            .where(SimulationRunModel.id == run_id)
        )
        if for_update:
            stmt = stmt.with_for_update()
        model = self.session.scalar(stmt)
        return None if model is None else self._domain(model)

    def save(self, item: SimulationRun, *, commit: bool = True) -> SimulationRun:
        model = self.session.get(SimulationRunModel, item.id)
        if model is None:
            raise ValueError("simulation run not found")
        self._apply(model, item)
        if commit:
            self._commit()
        else:
            self.session.flush()
        return self.get(item.id) or item

    def _commit(self) -> None:
        try:
            self.session.commit()
        except DBAPIError:
            self.session.rollback()
            raise

    def receipt(
        self, run_id: UUID, operation: str, simulation_event_id: UUID
    ) -> SimulationEventReceiptModel | None:
        return self.session.scalar(
            select(SimulationEventReceiptModel).where(
                SimulationEventReceiptModel.simulation_run_id == run_id,
                SimulationEventReceiptModel.operation == operation,
                SimulationEventReceiptModel.simulation_event_id == simulation_event_id,
            )
        )

    def add_receipt(
        self,
        *,
        run_id: UUID,
        event_id: UUID,
        operation: str,
        actor_id: UUID,
        simulated_at: datetime,
        request_sha256: str,
        resource_type: str | None,
        resource_id: UUID | None,
        response_status: int,
        response_snapshot: dict[str, Any],
        created_at: datetime,
    ) -> None:
        self.session.add(
            SimulationEventReceiptModel(
                id=uuid4(),
                simulation_run_id=run_id,
                simulation_event_id=event_id,
                operation=operation,
                actor_id=actor_id,
                simulated_at=simulated_at,
                request_sha256=request_sha256,
                resource_type=resource_type,
                resource_id=resource_id,
                response_status=response_status,
                response_snapshot=response_snapshot,
                created_at=created_at,
            )
        )
        self.session.flush()

    @staticmethod
    def _model(item: SimulationRun) -> SimulationRunModel:
        model = SimulationRunModel(id=item.id)
        SimulationRunRepository._apply(model, item)
        return model

    @staticmethod
    def _apply(model: SimulationRunModel, item: SimulationRun) -> None:
        model.status = item.status.value
        model.logical_start_at = item.logical_start_at
        model.logical_end_at = item.logical_end_at
        model.last_accepted_simulated_at = item.last_accepted_simulated_at
        model.credential_hash = item.credential_hash
        model.external_scenario_id = item.external_scenario_id
        model.external_scenario_version = item.external_scenario_version
        model.scenario_sha256 = item.scenario_sha256
        model.simulator_version = item.simulator_version
        model.created_by = item.created_by
        model.created_at = item.created_at
        model.updated_at = item.updated_at
        model.started_at = item.started_at
        model.completed_at = item.completed_at
        model.cancelled_at = item.cancelled_at
        model.facilities = [
            SimulationRunFacilityModel(simulation_run_id=item.id, facility_id=facility_id)
            for facility_id in item.facility_ids
        ]
        model.evdrivers = [
            SimulationRunEvDriverModel(simulation_run_id=item.id, user_id=user_id)
            for user_id in item.evdriver_ids
        ]

    @staticmethod
    def _domain(model: SimulationRunModel) -> SimulationRun:
        return SimulationRun(
            id=model.id,
            status=SimulationRunStatus(model.status),
            logical_start_at=_utc(model.logical_start_at),
            logical_end_at=_utc(model.logical_end_at),
            last_accepted_simulated_at=_utc_optional(model.last_accepted_simulated_at),
            credential_hash=model.credential_hash,
            facility_ids=tuple(item.facility_id for item in model.facilities),
            evdriver_ids=tuple(item.user_id for item in model.evdrivers),
            created_by=model.created_by,
            created_at=_utc(model.created_at),
            updated_at=_utc(model.updated_at),
            external_scenario_id=model.external_scenario_id,
            external_scenario_version=model.external_scenario_version,
            scenario_sha256=model.scenario_sha256,
            simulator_version=model.simulator_version,
            started_at=_utc_optional(model.started_at),
            completed_at=_utc_optional(model.completed_at),
            cancelled_at=_utc_optional(model.cancelled_at),
        )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _utc_optional(value: datetime | None) -> datetime | None:
    return None if value is None else _utc(value)
