from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import wraps
from time import monotonic
from typing import Literal, ParamSpec, TypeVar
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from opentelemetry import trace
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.charging.application.prediction import (
    PredictionInfrastructureReadPort,
    PredictionInfrastructureScope,
)
from app.modules.datasets.domain import ExportProfile, ExportStatus
from app.modules.datasets.prediction import PredictionDatasetProvenanceReadPort
from app.modules.identity.application.authorization import (
    Capability,
    has_capability,
    prediction_publisher_subject_id,
)
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.prediction.domain import (
    WEEKDAY_INDEX,
    WEEKDAYS,
    PredictionAuthorizationError,
    PredictionBucketCountError,
    PredictionBucketDuplicateError,
    PredictionBucketMissingError,
    PredictionCurrentNotFoundError,
    PredictionCycle,
    PredictionDatasetExportError,
    PredictionError,
    PredictionGranularity,
    PredictionHierarchyError,
    PredictionIdempotencyConflictError,
    PredictionNotFoundError,
    PredictionPersistenceError,
    PredictionRateError,
    PredictionScope,
    PredictionScopeIneligibleError,
    PredictionScopeType,
    PredictionTimezoneError,
    PredictionType,
    PublicationContent,
    Weekday,
)
from app.modules.prediction.infrastructure import (
    PredictionRepository,
    WeeklyOccupancyPredictionBucketModel,
    WeeklyOccupancyPredictionPublicationModel,
)
from app.modules.prediction.metrics import (
    authorization_failures_total,
    bucket_validation_failures_total,
    content_conflicts_total,
    idempotent_retries_total,
    missing_current_total,
    persistence_failures_total,
    publication_duration_seconds,
    publication_outcomes_total,
    queries_total,
    query_duration_seconds,
    recommendation_candidates,
    recommendations_total,
)
from app.shared.clock import Clock, SystemClock

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)
P = ParamSpec("P")
R = TypeVar("R")


def traced(operation: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(function: Callable[P, R]) -> Callable[P, R]:
        @wraps(function)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            with tracer.start_as_current_span(f"predictions.{operation}"):
                return function(*args, **kwargs)

        return wrapped

    return decorate


def _utc_from_db(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class PublicationResult:
    publication: WeeklyOccupancyPredictionPublicationModel
    is_current: bool
    idempotent_replay: bool


@dataclass(frozen=True, slots=True)
class PointResult:
    scope: PredictionScope
    day_of_week: Weekday
    hour_of_day: int
    timezone: str
    expected_occupancy_rate: float
    publication_id: UUID
    accepted_at: datetime
    technical_metadata_visible: bool


@dataclass(frozen=True, slots=True)
class RecommendationItem:
    facility_id: UUID
    station_id: UUID
    connector_id: UUID
    day_of_week: Weekday
    hour_of_day: int
    timezone: str
    facility_status: str
    station_status: str
    connector_status: str
    expected_occupancy_rate: float

    @property
    def expected_availability_rate(self) -> float:
        return 1.0 - self.expected_occupancy_rate


@dataclass(frozen=True, slots=True)
class RecommendationResult:
    input_type: Literal["TIMESTAMP", "LOCAL_WEEKDAY_HOUR"]
    timestamp: datetime | None
    day_of_week: Weekday | None
    hour_of_day: int | None
    items: tuple[RecommendationItem, ...]
    total: int
    limit: int
    offset: int
    shared_timezone: str | None = None
    shared_day_of_week: Weekday | None = None
    shared_hour_of_day: int | None = None


class PredictionService:
    def __init__(
        self,
        session: Session,
        infrastructure: PredictionInfrastructureReadPort,
        datasets: PredictionDatasetProvenanceReadPort,
        clock: Clock | None = None,
    ) -> None:
        self.session = session
        self.infrastructure = infrastructure
        self.datasets = datasets
        self.clock = clock or SystemClock()
        self.repository = PredictionRepository(session)

    @staticmethod
    def can_read_technical(user: User) -> bool:
        return has_capability(user, Capability.READ_TECHNICAL_PREDICTIONS)

    @staticmethod
    def _operator_facilities(user: User) -> tuple[UUID, ...] | None:
        if PredictionService.can_read_technical(user):
            return None
        if user.account_type == AccountType.HUMAN and HumanRole.FACILITY_OPERATOR in user.roles:
            return user.facility_ids
        raise PredictionAuthorizationError("Prediction resource is not visible.")

    @staticmethod
    def _scope_visible(user: User, facility_id: UUID) -> bool:
        return PredictionService.can_read_technical(user) or (
            user.account_type == AccountType.HUMAN
            and HumanRole.FACILITY_OPERATOR in user.roles
            and facility_id in user.facility_ids
        )

    def _resolve_scope(
        self, scope: PredictionScope, *, require_publication_eligibility: bool
    ) -> PredictionInfrastructureScope:
        scope.validate()
        try:
            resolved = self.infrastructure.resolve_scope(
                facility_id=scope.facility_id,
                station_id=scope.station_id,
                connector_id=scope.connector_id,
            )
        except LookupError as exc:
            raise PredictionNotFoundError(str(exc)) from exc
        except ValueError as exc:
            raise PredictionHierarchyError(str(exc)) from exc
        if require_publication_eligibility and not resolved.publication_eligible:
            raise PredictionScopeIneligibleError(
                "The infrastructure scope is not eligible to receive a publication."
            )
        return resolved

    def _validate_provenance(self, content: PublicationContent, publisher: User) -> None:
        if content.dataset_export_id is None:
            return
        provenance = self.datasets.get_for_prediction(content.dataset_export_id)
        if provenance is None:
            raise PredictionDatasetExportError("Dataset Export provenance was not found.")
        if provenance.status != ExportStatus.COMPLETED.value:
            raise PredictionDatasetExportError("Dataset Export provenance must be COMPLETED.")
        if provenance.export_profile != ExportProfile.RESEARCH.value:
            raise PredictionDatasetExportError("Dataset Export provenance must use RESEARCH.")
        admin = HumanRole.PLATFORM_ADMINISTRATOR in publisher.roles
        owned_research = provenance.requested_by == publisher.id and has_capability(
            publisher, Capability.RESEARCH_DATASET_EXPORT
        )
        if not admin and not owned_research:
            raise PredictionAuthorizationError("Dataset Export provenance is not visible.")
        filters = provenance.filters
        facility_id = filters.get("facility_id")
        station_id = filters.get("station_id")
        connector_id = filters.get("connector_id")
        if facility_id is not None and UUID(str(facility_id)) != content.scope.facility_id:
            raise PredictionDatasetExportError(
                "Dataset Export Facility scope is incompatible with the publication."
            )
        if station_id is not None and (
            content.scope.station_id is None or UUID(str(station_id)) != content.scope.station_id
        ):
            raise PredictionDatasetExportError(
                "Dataset Export Station scope is incompatible with the publication."
            )
        if connector_id is not None and (
            content.scope.connector_id is None
            or UUID(str(connector_id)) != content.scope.connector_id
        ):
            raise PredictionDatasetExportError(
                "Dataset Export Connector scope is incompatible with the publication."
            )

    def publish(self, *, content: PublicationContent, publisher: User) -> PublicationResult:
        started = monotonic()
        scope_type = content.scope.scope_type.value
        outcome = "rejected"
        with tracer.start_as_current_span("predictions.publish") as span:
            span.set_attribute("prediction.scope_type", scope_type)
            try:
                publisher_subject_id = prediction_publisher_subject_id(publisher)
            except PermissionError as exc:
                authorization_failures_total.labels("publish").inc()
                publication_outcomes_total.labels("rejected", scope_type).inc()
                publication_duration_seconds.labels("rejected").observe(monotonic() - started)
                raise PredictionAuthorizationError("Prediction publication is forbidden.") from exc
            try:
                resolved = self._resolve_scope(content.scope, require_publication_eligibility=True)
                if content.timezone != resolved.facility_timezone:
                    raise PredictionTimezoneError(
                        "Publication timezone must match the owning Facility timezone."
                    )
                self._validate_provenance(content, publisher)
                self.repository.lock_scope(content.scope.key)
                existing = self.repository.find_idempotency(
                    publisher_subject_id=publisher_subject_id,
                    external_run_id=content.external_run_id,
                    scope_key=content.scope.key,
                )
                if existing is not None:
                    if existing.canonical_content != content.canonical_json:
                        self.session.rollback()
                        content_conflicts_total.labels(scope_type).inc()
                        publication_outcomes_total.labels("conflict", scope_type).inc()
                        outcome = "conflict"
                        logger.warning(
                            "prediction_publication_content_conflict",
                            extra={
                                "scope_type": scope_type,
                                "existing_digest": existing.content_sha256,
                                "submitted_digest": content.sha256,
                            },
                        )
                        raise PredictionIdempotencyConflictError(
                            "The publication identity was reused with different canonical content."
                        )
                    is_current = self.repository.is_current(existing.id)
                    self.session.commit()
                    idempotent_retries_total.labels(scope_type).inc()
                    publication_outcomes_total.labels("idempotent_replay", scope_type).inc()
                    outcome = "idempotent_replay"
                    logger.info(
                        "prediction_publication_idempotent_replay",
                        extra={
                            "publication_id": str(existing.id),
                            "scope_type": scope_type,
                            "bucket_count": 168,
                        },
                    )
                    return PublicationResult(existing, is_current, True)

                accepted_at = self.clock.now().astimezone(UTC)
                publication = WeeklyOccupancyPredictionPublicationModel(
                    id=uuid4(),
                    prediction_type=PredictionType.WEEKLY_OCCUPANCY.value,
                    cycle=PredictionCycle.WEEKLY.value,
                    granularity=PredictionGranularity.HOUR.value,
                    scope_type=scope_type,
                    scope_key=content.scope.key,
                    facility_id=content.scope.facility_id,
                    station_id=content.scope.station_id,
                    connector_id=content.scope.connector_id,
                    timezone=content.timezone,
                    contract_version=content.contract_version,
                    model_name=content.model_name,
                    model_version=content.model_version,
                    external_run_id=content.external_run_id,
                    generated_at=content.generated_at,
                    accepted_at=accepted_at,
                    publisher_subject_id=publisher_subject_id,
                    dataset_export_id=content.dataset_export_id,
                    training_data_from=content.training_data_from,
                    training_data_to=content.training_data_to,
                    content_sha256=content.sha256,
                    canonical_content=content.canonical_json,
                )
                bucket_models = [
                    WeeklyOccupancyPredictionBucketModel(
                        publication_id=publication.id,
                        day_of_week=bucket.day_of_week.value,
                        hour_of_day=bucket.hour_of_day,
                        expected_occupancy_rate=float(bucket.expected_occupancy_rate),
                    )
                    for bucket in content.buckets
                ]
                self.repository.add_publication(publication, bucket_models)
                current = self.repository.current_reference(content.scope.key, for_update=True)
                becomes_current = False
                if current is None:
                    becomes_current = True
                else:
                    current_publication = self.repository.get(current.publication_id)
                    if current_publication is None:
                        raise PredictionPersistenceError(
                            "The current publication reference is inconsistent."
                        )
                    becomes_current = content.generated_at > _utc_from_db(
                        current_publication.generated_at
                    )
                if becomes_current:
                    self.repository.set_current(
                        scope=content.scope,
                        publication_id=publication.id,
                        accepted_at=accepted_at,
                    )
                self.session.commit()
                publication_outcomes_total.labels("accepted", scope_type).inc()
                outcome = "accepted"
                logger.info(
                    "prediction_publication_accepted",
                    extra={
                        "publication_id": str(publication.id),
                        "scope_type": scope_type,
                        "bucket_count": len(bucket_models),
                        "is_current": becomes_current,
                        "content_sha256": publication.content_sha256,
                    },
                )
                return PublicationResult(publication, becomes_current, False)
            except (
                PredictionBucketCountError,
                PredictionBucketDuplicateError,
                PredictionBucketMissingError,
                PredictionRateError,
            ) as exc:
                self.session.rollback()
                bucket_validation_failures_total.labels(exc.code).inc()
                publication_outcomes_total.labels("rejected", scope_type).inc()
                logger.warning(
                    "prediction_publication_validation_failed",
                    extra={"scope_type": scope_type, "reason": exc.code},
                )
                raise
            except PredictionError:
                self.session.rollback()
                if outcome == "rejected":
                    publication_outcomes_total.labels("rejected", scope_type).inc()
                raise
            except SQLAlchemyError as exc:
                self.session.rollback()
                persistence_failures_total.labels("publish").inc()
                publication_outcomes_total.labels("persistence_failure", scope_type).inc()
                outcome = "persistence_failure"
                logger.exception(
                    "prediction_publication_persistence_failed",
                    extra={"scope_type": scope_type},
                )
                raise PredictionPersistenceError(
                    "Prediction publication could not be stored."
                ) from exc
            finally:
                publication_duration_seconds.labels(outcome).observe(monotonic() - started)

    @traced("retrieve")
    def get(self, publication_id: UUID, *, actor: User) -> PublicationResult:
        started = monotonic()
        outcome = "not_found"
        try:
            publication = self.repository.get(publication_id)
            if publication is None or not self._scope_visible(actor, publication.facility_id):
                raise PredictionNotFoundError("Prediction publication was not found.")
            outcome = "success"
            return PublicationResult(publication, self.repository.is_current(publication.id), False)
        except PredictionAuthorizationError:
            authorization_failures_total.labels("retrieve").inc()
            outcome = "forbidden"
            raise
        finally:
            queries_total.labels("retrieve", outcome).inc()
            query_duration_seconds.labels("retrieve", outcome).observe(monotonic() - started)

    def profile(
        self, publication_id: UUID, *, actor: User
    ) -> tuple[PublicationResult, list[WeeklyOccupancyPredictionBucketModel]]:
        result = self.get(publication_id, actor=actor)
        buckets = self.repository.buckets(publication_id)
        if len(buckets) != 168:
            persistence_failures_total.labels("profile").inc()
            raise PredictionPersistenceError("Stored prediction profile is incomplete.")
        return result, buckets

    @traced("history")
    def history(
        self,
        *,
        actor: User,
        scope_type: PredictionScopeType | None,
        facility_id: UUID | None,
        station_id: UUID | None,
        connector_id: UUID | None,
        model_name: str | None,
        model_version: str | None,
        generated_from: datetime | None,
        generated_to: datetime | None,
        is_current: bool | None,
        limit: int,
        offset: int,
    ) -> tuple[list[PublicationResult], int]:
        started = monotonic()
        outcome = "success"
        try:
            if station_id is not None and facility_id is None:
                raise PredictionError("station_id requires facility_id.")
            if connector_id is not None and (facility_id is None or station_id is None):
                raise PredictionError("connector_id requires facility_id and station_id.")
            if generated_from is not None:
                generated_from = self._explicit_utc(generated_from, "generated_from")
            if generated_to is not None:
                generated_to = self._explicit_utc(generated_to, "generated_to")
            if (
                generated_from is not None
                and generated_to is not None
                and generated_from >= generated_to
            ):
                raise PredictionError("generated_from must be earlier than generated_to.")
            visible_facilities = self._operator_facilities(actor)
            if (
                visible_facilities is not None
                and facility_id is not None
                and facility_id not in visible_facilities
            ):
                raise PredictionAuthorizationError("Prediction scope is not visible.")
            rows, total = self.repository.list(
                scope_type=scope_type.value if scope_type else None,
                facility_id=facility_id,
                station_id=station_id,
                connector_id=connector_id,
                model_name=model_name,
                model_version=model_version,
                generated_from=generated_from,
                generated_to=generated_to,
                is_current=is_current,
                visible_facility_ids=visible_facilities,
                limit=limit,
                offset=offset,
            )
            return [PublicationResult(item, current, False) for item, current in rows], total
        except PredictionAuthorizationError:
            authorization_failures_total.labels("history").inc()
            outcome = "forbidden"
            raise
        except PredictionError:
            outcome = "invalid"
            raise
        finally:
            queries_total.labels("history", outcome).inc()
            query_duration_seconds.labels("history", outcome).observe(monotonic() - started)

    @traced("current")
    def current(self, scope: PredictionScope, *, actor: User) -> PublicationResult:
        started = monotonic()
        outcome = "success"
        try:
            self._resolve_scope(scope, require_publication_eligibility=False)
            if not self._scope_visible(actor, scope.facility_id):
                raise PredictionNotFoundError("Current prediction publication was not found.")
            publication = self.repository.current_publication(scope.key)
            if publication is None:
                missing_current_total.labels("current", scope.scope_type.value).inc()
                outcome = "not_found"
                raise PredictionCurrentNotFoundError(
                    "No current publication exists for this prediction scope."
                )
            return PublicationResult(publication, True, False)
        except PredictionNotFoundError:
            outcome = "not_found"
            raise
        except PredictionError:
            outcome = "invalid"
            raise
        finally:
            queries_total.labels("current", outcome).inc()
            query_duration_seconds.labels("current", outcome).observe(monotonic() - started)

    @staticmethod
    def _explicit_utc(value: datetime, field: str) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise PredictionError(f"{field} must include an explicit timezone offset.")
        return value.astimezone(UTC)

    @staticmethod
    def resolve_time(
        *,
        timezone: str,
        day_of_week: Weekday | None,
        hour_of_day: int | None,
        requested_timestamp: datetime | None,
    ) -> tuple[Weekday, int]:
        recurring = day_of_week is not None or hour_of_day is not None
        if requested_timestamp is not None and recurring:
            raise PredictionError("timestamp and day_of_week/hour_of_day are mutually exclusive.")
        if requested_timestamp is None:
            if day_of_week is None or hour_of_day is None:
                raise PredictionError(
                    "Provide either timestamp or both day_of_week and hour_of_day."
                )
            if not 0 <= hour_of_day <= 23:
                raise PredictionError("hour_of_day must be between 0 and 23.")
            return day_of_week, hour_of_day
        instant = PredictionService._explicit_utc(requested_timestamp, "timestamp")
        local = instant.astimezone(ZoneInfo(timezone))
        return WEEKDAYS[local.weekday()], local.hour

    def _driver_scope_eligible(
        self,
        scope: PredictionScope,
        resolved: PredictionInfrastructureScope,
        day: Weekday,
        hour: int,
    ) -> bool:
        index = WEEKDAY_INDEX[day]
        if scope.scope_type == PredictionScopeType.CONNECTOR:
            return resolved.driver_eligible(index, hour)
        candidates = self.infrastructure.connector_candidates(
            facility_id=scope.facility_id,
            station_id=scope.station_id,
        )
        return any(item.driver_eligible(index, hour) for item in candidates)

    @traced("point")
    def point(
        self,
        *,
        scope: PredictionScope,
        actor: User,
        day_of_week: Weekday | None,
        hour_of_day: int | None,
        requested_timestamp: datetime | None,
    ) -> PointResult:
        started = monotonic()
        outcome = "success"
        try:
            resolved = self._resolve_scope(scope, require_publication_eligibility=False)
            technical = self.can_read_technical(actor)
            operator = (
                actor.account_type == AccountType.HUMAN
                and HumanRole.FACILITY_OPERATOR in actor.roles
                and scope.facility_id in actor.facility_ids
            )
            driver = actor.account_type == AccountType.HUMAN and HumanRole.EV_DRIVER in actor.roles
            if not technical and not operator and not driver:
                authorization_failures_total.labels("point").inc()
                outcome = "forbidden"
                raise PredictionAuthorizationError("Prediction point lookup is forbidden.")
            publication = self.repository.current_publication(scope.key)
            if publication is None:
                missing_current_total.labels("point", scope.scope_type.value).inc()
                outcome = "not_found"
                raise PredictionCurrentNotFoundError(
                    "No current publication exists for this prediction scope."
                )
            day, hour = self.resolve_time(
                timezone=publication.timezone,
                day_of_week=day_of_week,
                hour_of_day=hour_of_day,
                requested_timestamp=requested_timestamp,
            )
            if driver and not self._driver_scope_eligible(scope, resolved, day, hour):
                outcome = "not_found"
                raise PredictionNotFoundError("Prediction scope is not currently eligible.")
            row = self.repository.current_bucket(
                scope_key=scope.key, day_of_week=day, hour_of_day=hour
            )
            if row is None:
                persistence_failures_total.labels("point").inc()
                outcome = "persistence_failure"
                raise PredictionPersistenceError("Current prediction bucket is missing.")
            _, bucket = row
            return PointResult(
                scope=scope,
                day_of_week=day,
                hour_of_day=hour,
                timezone=publication.timezone,
                expected_occupancy_rate=bucket.expected_occupancy_rate,
                publication_id=publication.id,
                accepted_at=publication.accepted_at,
                technical_metadata_visible=technical or operator,
            )
        except PredictionError:
            if outcome == "success":
                outcome = "invalid"
            raise
        finally:
            queries_total.labels("point", outcome).inc()
            query_duration_seconds.labels("point", outcome).observe(monotonic() - started)

    @traced("recommendation")
    def recommend_connectors(
        self,
        *,
        actor: User,
        day_of_week: Weekday | None,
        hour_of_day: int | None,
        requested_timestamp: datetime | None,
        facility_id: UUID | None,
        station_id: UUID | None,
        limit: int,
        offset: int,
        station_specific: bool = False,
    ) -> RecommendationResult:
        started = monotonic()
        outcome = "success"
        try:
            if not (
                actor.status == AccountStatus.ACTIVE
                and actor.account_type == AccountType.HUMAN
                and HumanRole.EV_DRIVER in actor.roles
            ):
                authorization_failures_total.labels("recommendation").inc()
                outcome = "forbidden"
                raise PredictionAuthorizationError("EVDriver recommendation access is required.")
            if station_specific and station_id is None:
                raise PredictionError("station_id is required.")
            if facility_id is not None:
                self._resolve_scope(
                    PredictionScope(
                        PredictionScopeType.STATION if station_id else PredictionScopeType.FACILITY,
                        facility_id,
                        station_id,
                    ),
                    require_publication_eligibility=False,
                )
            candidates = self.infrastructure.connector_candidates(
                facility_id=facility_id, station_id=station_id
            )
            if station_id is not None and not candidates:
                raise PredictionNotFoundError("Charging Station was not found.")
            items: list[RecommendationItem] = []
            for candidate in candidates:
                if candidate.station_id is None or candidate.connector_id is None:
                    persistence_failures_total.labels("recommendation").inc()
                    raise PredictionPersistenceError(
                        "Connector recommendation hierarchy is inconsistent."
                    )
                scope = PredictionScope(
                    PredictionScopeType.CONNECTOR,
                    candidate.facility_id,
                    candidate.station_id,
                    candidate.connector_id,
                )
                publication = self.repository.current_publication(scope.key)
                if publication is None:
                    missing_current_total.labels(
                        "recommendation", PredictionScopeType.CONNECTOR.value
                    ).inc()
                    continue
                day, hour = self.resolve_time(
                    timezone=publication.timezone,
                    day_of_week=day_of_week,
                    hour_of_day=hour_of_day,
                    requested_timestamp=requested_timestamp,
                )
                if not candidate.driver_eligible(WEEKDAY_INDEX[day], hour):
                    continue
                row = self.repository.current_bucket(
                    scope_key=scope.key, day_of_week=day, hour_of_day=hour
                )
                if row is None:
                    persistence_failures_total.labels("recommendation").inc()
                    continue
                _, bucket = row
                items.append(
                    RecommendationItem(
                        facility_id=candidate.facility_id,
                        station_id=candidate.station_id,
                        connector_id=candidate.connector_id,
                        day_of_week=day,
                        hour_of_day=hour,
                        timezone=publication.timezone,
                        facility_status=candidate.facility_status,
                        station_status=candidate.station_status or "",
                        connector_status=candidate.connector_status or "",
                        expected_occupancy_rate=bucket.expected_occupancy_rate,
                    )
                )
            items.sort(
                key=lambda item: (
                    -item.expected_availability_rate,
                    str(item.facility_id),
                    str(item.station_id),
                    str(item.connector_id),
                )
            )
            total = len(items)
            selected = tuple(items[offset : offset + limit])
            shared_timezone = None
            shared_day = None
            shared_hour = None
            if station_specific and selected:
                time_keys = {
                    (item.timezone, item.day_of_week, item.hour_of_day) for item in selected
                }
                if len(time_keys) == 1:
                    shared_timezone, shared_day, shared_hour = next(iter(time_keys))
            recommendation_candidates.labels("success").observe(total)
            recommendations_total.labels("success").inc()
            logger.info(
                "prediction_recommendation_completed",
                extra={
                    "outcome": "success",
                    "candidate_count": total,
                    "station_specific": station_specific,
                },
            )
            return RecommendationResult(
                input_type="TIMESTAMP" if requested_timestamp is not None else "LOCAL_WEEKDAY_HOUR",
                timestamp=requested_timestamp,
                day_of_week=day_of_week,
                hour_of_day=hour_of_day,
                items=selected,
                total=total,
                limit=limit,
                offset=offset,
                shared_timezone=shared_timezone,
                shared_day_of_week=shared_day,
                shared_hour_of_day=shared_hour,
            )
        except (PredictionError, PredictionPersistenceError) as exc:
            if outcome == "success":
                outcome = (
                    "persistence_failure"
                    if isinstance(exc, PredictionPersistenceError)
                    else "invalid"
                )
            recommendation_candidates.labels(outcome).observe(0)
            recommendations_total.labels(outcome).inc()
            raise
        finally:
            query_duration_seconds.labels("recommendation", outcome).observe(monotonic() - started)
