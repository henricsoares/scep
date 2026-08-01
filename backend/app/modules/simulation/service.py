from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.charging.infrastructure.charging_session_model import ChargingSessionModel
from app.modules.charging.infrastructure.facility_model import FacilityModel
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from app.modules.simulation.domain import SimulationRun, SimulationRunStatus
from app.modules.simulation.infrastructure import SimulationRunRepository
from app.modules.simulation.security import issue_run_credential
from app.shared.clock import Clock


class SimulationRunNotFoundError(Exception):
    pass


class SimulationRunActiveSessionsError(Exception):
    pass


class SimulationRunService:
    def __init__(self, session: Session, clock: Clock) -> None:
        self.session = session
        self.clock = clock
        self.runs = SimulationRunRepository(session)
        self.users = SqlAlchemyUserRepository(session)

    def create(
        self,
        *,
        logical_start_at: datetime,
        logical_end_at: datetime,
        facility_ids: list[UUID],
        evdriver_ids: list[UUID],
        created_by: UUID,
        external_scenario_id: str | None,
        external_scenario_version: str | None,
        scenario_sha256: str | None,
        simulator_version: str | None,
    ) -> SimulationRun:
        self._validate_associations(facility_ids, evdriver_ids, require_nonempty=False)
        item = SimulationRun.create(
            logical_start_at=logical_start_at,
            logical_end_at=logical_end_at,
            facility_ids=facility_ids,
            evdriver_ids=evdriver_ids,
            created_by=created_by,
            now=self.clock.now(),
            external_scenario_id=external_scenario_id,
            external_scenario_version=external_scenario_version,
            scenario_sha256=scenario_sha256,
            simulator_version=simulator_version,
        )
        return self.runs.add(item)

    def get(self, run_id: UUID) -> SimulationRun:
        item = self.runs.get(run_id)
        if item is None:
            raise SimulationRunNotFoundError("simulation run not found")
        return item

    def update(
        self,
        run_id: UUID,
        *,
        logical_start_at: datetime | None,
        logical_end_at: datetime | None,
        facility_ids: list[UUID] | None,
        evdriver_ids: list[UUID] | None,
        external_scenario_id: str | None,
        external_scenario_version: str | None,
        scenario_sha256: str | None,
        simulator_version: str | None,
    ) -> SimulationRun:
        item = self.get(run_id)
        target_facilities = list(item.facility_ids) if facility_ids is None else facility_ids
        target_evdrivers = list(item.evdriver_ids) if evdriver_ids is None else evdriver_ids
        self._validate_associations(target_facilities, target_evdrivers, require_nonempty=False)
        updated = item.update_draft(
            now=self.clock.now(),
            logical_start_at=logical_start_at,
            logical_end_at=logical_end_at,
            facility_ids=facility_ids,
            evdriver_ids=evdriver_ids,
            external_scenario_id=external_scenario_id,
            external_scenario_version=external_scenario_version,
            scenario_sha256=scenario_sha256,
            simulator_version=simulator_version,
        )
        return self.runs.save(updated)

    def start(self, run_id: UUID) -> tuple[SimulationRun, str]:
        item = self._locked(run_id)
        self._validate_associations(
            list(item.facility_ids), list(item.evdriver_ids), require_nonempty=True
        )
        plaintext, credential_hash = issue_run_credential()
        return (
            self.runs.save(item.start(credential_hash=credential_hash, now=self.clock.now())),
            plaintext,
        )

    def complete(self, run_id: UUID) -> SimulationRun:
        item = self._locked(run_id)
        active = self.session.scalar(
            select(ChargingSessionModel.id)
            .where(
                ChargingSessionModel.simulation_run_id == run_id,
                ChargingSessionModel.status == "ACTIVE",
            )
            .limit(1)
        )
        if active is not None:
            self.session.rollback()
            raise SimulationRunActiveSessionsError("simulation run has ACTIVE charging sessions")
        return self.runs.save(item.complete(now=self.clock.now()))

    def cancel(self, run_id: UUID) -> SimulationRun:
        item = self._locked(run_id)
        return self.runs.save(item.cancel(now=self.clock.now()))

    def _locked(self, run_id: UUID) -> SimulationRun:
        item = self.runs.get(run_id, for_update=True)
        if item is None:
            raise SimulationRunNotFoundError("simulation run not found")
        return item

    def _validate_associations(
        self, facility_ids: list[UUID], evdriver_ids: list[UUID], *, require_nonempty: bool
    ) -> None:
        unique_facilities = set(facility_ids)
        unique_drivers = set(evdriver_ids)
        if require_nonempty and (not unique_facilities or not unique_drivers):
            raise ValueError("run requires at least one Facility and one EVDriver")
        found_facilities = set(
            self.session.scalars(
                select(FacilityModel.id).where(FacilityModel.id.in_(unique_facilities))
            ).all()
        )
        if found_facilities != unique_facilities:
            raise ValueError("one or more Facilities do not exist")
        for user_id in unique_drivers:
            user = self.users.get(user_id)
            if (
                user is None
                or user.status != AccountStatus.ACTIVE
                or user.account_type != AccountType.HUMAN
                or HumanRole.EV_DRIVER not in user.roles
            ):
                raise ValueError("one or more EVDrivers are not active EVDriver Users")

    @staticmethod
    def is_running(item: SimulationRun) -> bool:
        return item.status == SimulationRunStatus.RUNNING
