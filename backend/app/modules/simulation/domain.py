from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include an explicit offset")
    return value.astimezone(UTC)


class SimulationRunStatus(StrEnum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


@dataclass(frozen=True, slots=True)
class SimulationRun:
    id: UUID
    status: SimulationRunStatus
    logical_start_at: datetime
    logical_end_at: datetime
    last_accepted_simulated_at: datetime | None
    credential_hash: str | None
    facility_ids: tuple[UUID, ...]
    evdriver_ids: tuple[UUID, ...]
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    external_scenario_id: str | None = None
    external_scenario_version: str | None = None
    scenario_sha256: str | None = None
    simulator_version: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        logical_start_at: datetime,
        logical_end_at: datetime,
        facility_ids: list[UUID],
        evdriver_ids: list[UUID],
        created_by: UUID,
        now: datetime,
        external_scenario_id: str | None = None,
        external_scenario_version: str | None = None,
        scenario_sha256: str | None = None,
        simulator_version: str | None = None,
    ) -> SimulationRun:
        current = utc(now)
        item = cls(
            id=uuid4(),
            status=SimulationRunStatus.DRAFT,
            logical_start_at=utc(logical_start_at),
            logical_end_at=utc(logical_end_at),
            last_accepted_simulated_at=None,
            credential_hash=None,
            facility_ids=tuple(dict.fromkeys(facility_ids)),
            evdriver_ids=tuple(dict.fromkeys(evdriver_ids)),
            created_by=created_by,
            created_at=current,
            updated_at=current,
            external_scenario_id=_optional(external_scenario_id),
            external_scenario_version=_optional(external_scenario_version),
            scenario_sha256=_sha256(scenario_sha256),
            simulator_version=_optional(simulator_version),
        )
        item.validate()
        return item

    def validate(self) -> None:
        if self.logical_start_at >= self.logical_end_at:
            raise ValueError("logical_start_at must precede logical_end_at")
        if self.last_accepted_simulated_at is not None and not (
            self.logical_start_at <= self.last_accepted_simulated_at <= self.logical_end_at
        ):
            raise ValueError("last accepted simulated time must be inside the logical window")
        if self.status == SimulationRunStatus.RUNNING and (
            not self.credential_hash or self.started_at is None
        ):
            raise ValueError("RUNNING run requires credential and started_at")
        if self.status == SimulationRunStatus.COMPLETED and self.completed_at is None:
            raise ValueError("COMPLETED run requires completed_at")
        if self.status == SimulationRunStatus.CANCELLED and self.cancelled_at is None:
            raise ValueError("CANCELLED run requires cancelled_at")

    def update_draft(
        self,
        *,
        now: datetime,
        logical_start_at: datetime | None = None,
        logical_end_at: datetime | None = None,
        facility_ids: list[UUID] | None = None,
        evdriver_ids: list[UUID] | None = None,
        external_scenario_id: str | None = None,
        external_scenario_version: str | None = None,
        scenario_sha256: str | None = None,
        simulator_version: str | None = None,
    ) -> SimulationRun:
        if self.status != SimulationRunStatus.DRAFT:
            raise ValueError("only DRAFT runs may be updated")
        item = replace(
            self,
            logical_start_at=(
                self.logical_start_at if logical_start_at is None else utc(logical_start_at)
            ),
            logical_end_at=self.logical_end_at if logical_end_at is None else utc(logical_end_at),
            facility_ids=(
                self.facility_ids if facility_ids is None else tuple(dict.fromkeys(facility_ids))
            ),
            evdriver_ids=(
                self.evdriver_ids if evdriver_ids is None else tuple(dict.fromkeys(evdriver_ids))
            ),
            external_scenario_id=_optional(external_scenario_id),
            external_scenario_version=_optional(external_scenario_version),
            scenario_sha256=_sha256(scenario_sha256),
            simulator_version=_optional(simulator_version),
            updated_at=utc(now),
        )
        item.validate()
        return item

    def start(self, *, credential_hash: str, now: datetime) -> SimulationRun:
        if self.status != SimulationRunStatus.DRAFT:
            raise ValueError("only DRAFT runs may be started")
        if not self.facility_ids or not self.evdriver_ids:
            raise ValueError("run requires at least one Facility and one EVDriver")
        current = utc(now)
        item = replace(
            self,
            status=SimulationRunStatus.RUNNING,
            credential_hash=credential_hash,
            started_at=current,
            updated_at=current,
        )
        item.validate()
        return item

    def complete(self, *, now: datetime) -> SimulationRun:
        if self.status != SimulationRunStatus.RUNNING:
            raise ValueError("only RUNNING runs may be completed")
        current = utc(now)
        item = replace(
            self,
            status=SimulationRunStatus.COMPLETED,
            completed_at=current,
            updated_at=current,
        )
        item.validate()
        return item

    def cancel(self, *, now: datetime) -> SimulationRun:
        if self.status not in {SimulationRunStatus.DRAFT, SimulationRunStatus.RUNNING}:
            raise ValueError("only DRAFT or RUNNING runs may be cancelled")
        current = utc(now)
        item = replace(
            self,
            status=SimulationRunStatus.CANCELLED,
            credential_hash=None,
            cancelled_at=current,
            updated_at=current,
        )
        item.validate()
        return item


def _optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _sha256(value: str | None) -> str | None:
    normalized = _optional(value)
    if normalized is None:
        return None
    lowered = normalized.lower()
    if len(lowered) != 64 or any(char not in "0123456789abcdef" for char in lowered):
        raise ValueError("scenario_sha256 must contain 64 lowercase hexadecimal characters")
    return lowered
