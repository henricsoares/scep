from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RangeInt(BaseModel):
    min: int = Field(ge=0)
    max: int = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self) -> "RangeInt":
        if self.min > self.max:
            raise ValueError("min must not exceed max")
        return self


class RangeFloat(BaseModel):
    min: float = Field(ge=0)
    max: float = Field(ge=0)

    @model_validator(mode="after")
    def ordered(self) -> "RangeFloat":
        if self.min > self.max:
            raise ValueError("min must not exceed max")
        return self


class TelemetryConfig(BaseModel):
    enabled: bool = True
    sampling_interval_minutes: int = Field(default=15, ge=1)
    batch_size: int = Field(default=100, ge=1, le=1000)
    bounded_power_noise: float = Field(default=0, ge=0, le=1)


class FailureHandling(BaseModel):
    try_another_connector: bool = True
    try_another_station: bool = True
    try_another_facility: bool = True
    maximum_alternative_attempts: int = Field(default=3, ge=0)
    rescheduling_delay_minutes: RangeInt = Field(
        default_factory=lambda: RangeInt(min=15, max=60)
    )
    maximum_rescheduling_attempts: int = Field(default=2, ge=0)


class DriverBehavior(BaseModel):
    driver_id: UUID
    sessions_per_week: RangeInt
    weekday_weights: dict[int, float]
    hour_weights: dict[int, float]
    start_time_jitter_minutes: int = Field(default=0, ge=0, le=59)
    facility_weights: dict[UUID, float] = Field(default_factory=dict)
    preferred_connector_types: list[str] = Field(default_factory=list)
    selection_strategy: Literal["WEIGHTED_RANDOM", "FIRST_ELIGIBLE"] = "WEIGHTED_RANDOM"
    reservation_probability: float = Field(default=1, ge=0, le=1)
    cancellation_probability: float = Field(default=0, ge=0, le=1)
    no_show_probability: float = Field(default=0, ge=0, le=1)
    lead_time_minutes: RangeInt = Field(
        default_factory=lambda: RangeInt(min=30, max=120)
    )
    session_duration_minutes: RangeInt = Field(
        default_factory=lambda: RangeInt(min=30, max=90)
    )
    power_utilization_factor: RangeFloat = Field(
        default_factory=lambda: RangeFloat(min=0.5, max=0.9)
    )
    telemetry: TelemetryConfig | None = None
    failure_handling: FailureHandling = Field(default_factory=FailureHandling)

    @model_validator(mode="after")
    def valid_probabilities_and_weights(self) -> "DriverBehavior":
        if self.cancellation_probability + self.no_show_probability > 1:
            raise ValueError(
                "cancellation_probability plus no_show_probability must not exceed one"
            )
        if (
            self.session_duration_minutes.min < 15
            or self.session_duration_minutes.max > 1440
        ):
            raise ValueError("session duration must remain between 15 and 1440 minutes")
        if self.power_utilization_factor.max > 1:
            raise ValueError("power utilization factor must not exceed one")
        if not self.weekday_weights or any(
            day not in range(7) for day in self.weekday_weights
        ):
            raise ValueError("weekday_weights must use days 0 through 6")
        if not self.hour_weights or any(
            hour not in range(24) for hour in self.hour_weights
        ):
            raise ValueError("hour_weights must use hours 0 through 23")
        for weights in (self.weekday_weights, self.hour_weights, self.facility_weights):
            if any(value < 0 for value in weights.values()) or (
                weights and sum(weights.values()) <= 0
            ):
                raise ValueError("weights must be non-negative with a positive total")
        return self


class Scenario(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    scenario_id: str = Field(min_length=1, max_length=255)
    scenario_version: str = Field(min_length=1, max_length=128)
    random_seed: int
    logical_start_at: datetime
    logical_end_at: datetime
    telemetry_defaults: TelemetryConfig = Field(default_factory=TelemetryConfig)
    drivers: list[DriverBehavior] = Field(min_length=1)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def valid_window_and_drivers(self) -> "Scenario":
        if self.logical_start_at.tzinfo is None or self.logical_end_at.tzinfo is None:
            raise ValueError("logical timestamps require explicit offsets")
        if self.logical_start_at >= self.logical_end_at:
            raise ValueError("logical_start_at must precede logical_end_at")
        ids = [item.driver_id for item in self.drivers]
        if len(ids) != len(set(ids)):
            raise ValueError("driver_id must be unique")
        return self

    def canonical_digest(self) -> str:
        content = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        ).encode()
        return hashlib.sha256(content).hexdigest()


class BootstrapRun(BaseModel):
    id: UUID
    status: Literal["RUNNING"]
    logical_start_at: datetime
    logical_end_at: datetime


class Bootstrap(BaseModel):
    bootstrap_version: Literal["1.0"]
    api_version: Literal["1"]
    generated_at: datetime
    simulation_run: BootstrapRun
    authorized_facility_ids: list[UUID]
    authorized_evdriver_ids: list[UUID]
    model_config = ConfigDict(extra="forbid")
