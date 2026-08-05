from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.charging.infrastructure.prediction_reader import ChargingPredictionReader
from app.modules.datasets.prediction import DatasetPredictionReader
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.domain.user import User
from app.modules.prediction.domain import (
    PredictionBucket,
    PredictionBucketCountError,
    PredictionBucketDuplicateError,
    PredictionBucketMissingError,
    PredictionCycle,
    PredictionError,
    PredictionGranularity,
    PredictionPersistenceError,
    PredictionRateError,
    PredictionScope,
    PredictionScopeType,
    PredictionType,
    PublicationContent,
    Weekday,
)
from app.modules.prediction.infrastructure import (
    WeeklyOccupancyPredictionBucketModel,
    WeeklyOccupancyPredictionPublicationModel,
)
from app.modules.prediction.metrics import (
    bucket_validation_failures_total,
    publication_outcomes_total,
)
from app.modules.prediction.service import (
    PointResult,
    PredictionService,
    PublicationResult,
    RecommendationResult,
)

router = APIRouter(prefix="/predictions", tags=["Weekly Occupancy Predictions"])
logger = logging.getLogger(__name__)


class PredictionScopeResponse(BaseModel):
    scope_type: PredictionScopeType
    facility_id: UUID
    station_id: UUID | None = None
    connector_id: UUID | None = None


class PredictionBucketRequest(BaseModel):
    day_of_week: Weekday
    hour_of_day: int = Field(strict=True, ge=0, le=23)
    expected_occupancy_rate: float = Field(strict=True, ge=0, le=1, allow_inf_nan=False)
    model_config = ConfigDict(extra="forbid")

    def domain(self) -> PredictionBucket:
        return PredictionBucket(self.day_of_week, self.hour_of_day, self.expected_occupancy_rate)


class PredictionBucketResponse(BaseModel):
    day_of_week: Weekday
    hour_of_day: int = Field(ge=0, le=23)
    expected_occupancy_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    expected_availability_rate: float = Field(ge=0, le=1, allow_inf_nan=False)


class PublishWeeklyOccupancyRequest(BaseModel):
    contract_version: Literal["1.0"] = "1.0"
    prediction_type: Literal[PredictionType.WEEKLY_OCCUPANCY] = PredictionType.WEEKLY_OCCUPANCY
    scope_type: PredictionScopeType
    facility_id: UUID
    station_id: UUID | None = None
    connector_id: UUID | None = None
    timezone: str = Field(min_length=1, max_length=128)
    model_name: str = Field(min_length=1, max_length=255)
    model_version: str = Field(min_length=1, max_length=128)
    external_run_id: str = Field(min_length=1, max_length=255)
    generated_at: datetime
    dataset_export_id: UUID | None = None
    training_data_from: datetime | None = None
    training_data_to: datetime | None = None
    buckets: list[PredictionBucketRequest] = Field(min_length=168, max_length=168)
    model_config = ConfigDict(extra="forbid")

    def content(self) -> PublicationContent:
        return PublicationContent.create(
            scope=PredictionScope(
                self.scope_type,
                self.facility_id,
                self.station_id,
                self.connector_id,
            ),
            timezone=self.timezone,
            contract_version=self.contract_version,
            model_name=self.model_name,
            model_version=self.model_version,
            external_run_id=self.external_run_id,
            generated_at=self.generated_at,
            dataset_export_id=self.dataset_export_id,
            training_data_from=self.training_data_from,
            training_data_to=self.training_data_to,
            buckets=[item.domain() for item in self.buckets],
        )


class PublicationLinks(BaseModel):
    self: str
    profile: str


class PublicationSummaryResponse(BaseModel):
    id: UUID
    prediction_type: PredictionType
    cycle: PredictionCycle
    granularity: PredictionGranularity
    scope: PredictionScopeResponse
    timezone: str
    contract_version: str
    model_name: str | None = None
    model_version: str | None = None
    external_run_id: str | None = None
    generated_at: datetime
    accepted_at: datetime
    publisher_subject_id: UUID | None = None
    dataset_export_id: UUID | None = None
    training_data_from: datetime | None = None
    training_data_to: datetime | None = None
    bucket_count: Literal[168] = 168
    content_sha256: str | None = None
    is_current: bool
    idempotent_replay: bool | None = None
    links: PublicationLinks


class PublicationHistoryResponse(BaseModel):
    items: list[PublicationSummaryResponse]
    limit: int
    offset: int
    total: int


class PublicationProfileResponse(BaseModel):
    publication_id: UUID
    prediction_type: PredictionType
    scope: PredictionScopeResponse
    timezone: str
    basis: Literal["RECURRING_WEEKLY_PATTERN"] = "RECURRING_WEEKLY_PATTERN"
    bucket_count: Literal[168] = 168
    buckets: list[PredictionBucketResponse]


class CurrentPublicationResponse(PublicationSummaryResponse):
    buckets: list[PredictionBucketResponse] | None = None


class PredictionPointResponse(BaseModel):
    scope: PredictionScopeResponse
    day_of_week: Weekday
    hour_of_day: int
    timezone: str
    expected_occupancy_rate: float
    expected_availability_rate: float
    publication_id: UUID | None = None
    accepted_at: datetime | None = None
    basis: Literal["RECURRING_WEEKLY_PATTERN"] = "RECURRING_WEEKLY_PATTERN"
    availability_guaranteed: Literal[False] = False


class ResolvedRecommendationTime(BaseModel):
    day_of_week: Weekday
    hour_of_day: int
    timezone: str


class RecommendationRequestTime(BaseModel):
    input_type: Literal["TIMESTAMP", "LOCAL_WEEKDAY_HOUR"]
    timestamp: datetime | None = None
    day_of_week: Weekday | None = None
    hour_of_day: int | None = None


class ConnectorRecommendationItem(BaseModel):
    rank: int
    facility_id: UUID
    station_id: UUID
    connector_id: UUID
    resolved_time: ResolvedRecommendationTime
    facility_status: str
    station_status: str
    connector_status: str
    expected_occupancy_rate: float
    expected_availability_rate: float


class ConnectorRecommendationResponse(BaseModel):
    request_time: RecommendationRequestTime
    resolved_time: ResolvedRecommendationTime | None = None
    basis: Literal["RECURRING_WEEKLY_PATTERN"] = "RECURRING_WEEKLY_PATTERN"
    availability_guaranteed: Literal[False] = False
    reservation_created: Literal[False] = False
    items: list[ConnectorRecommendationItem]
    limit: int
    offset: int
    total: int


ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"description": "Invalid prediction hierarchy, timezone, period, or time input"},
    401: {"description": "Authentication required"},
    403: {"description": "Prediction access forbidden"},
    404: {"description": "Prediction or visible infrastructure not found"},
    409: {"description": "Prediction publication idempotency conflict"},
    422: {"description": "Invalid publication schema or weekly bucket profile"},
    500: {"description": "Atomic prediction persistence failed"},
}


def prediction_service(db: Annotated[Session, Depends(get_db)]) -> PredictionService:
    return PredictionService(
        db,
        ChargingPredictionReader(db),
        DatasetPredictionReader(db),
    )


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", request.headers.get("x-request-id") or uuid4()))


def _utc_timestamp(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _http_error(request: Request, exc: Exception) -> HTTPException:
    code = getattr(exc, "code", "PREDICTION_INVALID")
    status_code = getattr(exc, "status_code", 500)
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": str(exc), "request_id": _request_id(request)},
    )


def _run[T](request: Request, operation: Callable[[], T]) -> T:
    try:
        return operation()
    except (PredictionError, PredictionPersistenceError) as exc:
        raise _http_error(request, exc) from exc


def _scope(
    scope_type: PredictionScopeType,
    facility_id: UUID,
    station_id: UUID | None,
    connector_id: UUID | None,
) -> PredictionScope:
    return PredictionScope(scope_type, facility_id, station_id, connector_id)


def _technical_summary(
    result: PublicationResult, *, technical_metadata: bool
) -> PublicationSummaryResponse:
    item = result.publication
    base: dict[str, Any] = {
        "id": item.id,
        "prediction_type": item.prediction_type,
        "cycle": item.cycle,
        "granularity": item.granularity,
        "scope": {
            "scope_type": item.scope_type,
            "facility_id": item.facility_id,
            "station_id": item.station_id,
            "connector_id": item.connector_id,
        },
        "timezone": item.timezone,
        "contract_version": item.contract_version,
        "generated_at": _utc_timestamp(item.generated_at),
        "accepted_at": _utc_timestamp(item.accepted_at),
        "bucket_count": 168,
        "is_current": result.is_current,
        "idempotent_replay": result.idempotent_replay if result.idempotent_replay else None,
        "links": {
            "self": f"/predictions/weekly-occupancy-publications/{item.id}",
            "profile": f"/predictions/weekly-occupancy-publications/{item.id}/profile",
        },
    }
    if technical_metadata:
        base.update(
            {
                "model_name": item.model_name,
                "model_version": item.model_version,
                "external_run_id": item.external_run_id,
                "publisher_subject_id": item.publisher_subject_id,
                "dataset_export_id": item.dataset_export_id,
                "training_data_from": _utc_timestamp(item.training_data_from),
                "training_data_to": _utc_timestamp(item.training_data_to),
                "content_sha256": item.content_sha256,
            }
        )
    return PublicationSummaryResponse.model_validate(base)


def _bucket(item: WeeklyOccupancyPredictionBucketModel) -> PredictionBucketResponse:
    return PredictionBucketResponse(
        day_of_week=Weekday(item.day_of_week),
        hour_of_day=item.hour_of_day,
        expected_occupancy_rate=item.expected_occupancy_rate,
        expected_availability_rate=1.0 - item.expected_occupancy_rate,
    )


def _profile(
    publication: WeeklyOccupancyPredictionPublicationModel,
    buckets: list[WeeklyOccupancyPredictionBucketModel],
) -> PublicationProfileResponse:
    return PublicationProfileResponse(
        publication_id=publication.id,
        prediction_type=PredictionType(publication.prediction_type),
        scope=PredictionScopeResponse(
            scope_type=PredictionScopeType(publication.scope_type),
            facility_id=publication.facility_id,
            station_id=publication.station_id,
            connector_id=publication.connector_id,
        ),
        timezone=publication.timezone,
        buckets=[_bucket(item) for item in buckets],
    )


@router.post(
    "/weekly-occupancy-publications",
    response_model=PublicationSummaryResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    responses=ERRORS,
    summary="Publish one complete recurring weekly occupancy profile",
    description=(
        "Accepts exactly 168 unique weekday/hour buckets generated externally. "
        "The Backend validates and stores results but performs no training or inference."
    ),
)
def publish_weekly_occupancy(
    payload: PublishWeeklyOccupancyRequest,
    response: Response,
    request: Request,
    service: Annotated[PredictionService, Depends(prediction_service)],
    publisher: Annotated[User, Depends(current_user)],
) -> PublicationSummaryResponse:
    try:
        service.authorize_publication(publisher=publisher, scope_type=payload.scope_type)
        content = payload.content()
        result = service.publish(content=content, publisher=publisher)
    except (
        PredictionBucketCountError,
        PredictionBucketDuplicateError,
        PredictionBucketMissingError,
        PredictionRateError,
    ) as exc:
        bucket_validation_failures_total.labels(exc.code).inc()
        publication_outcomes_total.labels("rejected", payload.scope_type.value).inc()
        logger.warning(
            "prediction_publication_validation_failed",
            extra={"scope_type": payload.scope_type.value, "reason": exc.code},
        )
        raise _http_error(request, exc) from exc
    except (PredictionError, PredictionPersistenceError) as exc:
        raise _http_error(request, exc) from exc
    if result.idempotent_replay:
        response.status_code = status.HTTP_200_OK
    else:
        response.status_code = status.HTTP_201_CREATED
        response.headers["Location"] = (
            f"/predictions/weekly-occupancy-publications/{result.publication.id}"
        )
    summary = _technical_summary(result, technical_metadata=True)
    summary.idempotent_replay = result.idempotent_replay
    return summary


@router.get(
    "/weekly-occupancy-publications",
    response_model=PublicationHistoryResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
    summary="List visible weekly occupancy publication history",
)
def list_weekly_occupancy_publications(
    request: Request,
    service: Annotated[PredictionService, Depends(prediction_service)],
    actor: Annotated[User, Depends(current_user)],
    scope_type: PredictionScopeType | None = None,
    facility_id: UUID | None = None,
    station_id: UUID | None = None,
    connector_id: UUID | None = None,
    model_name: str | None = None,
    model_version: str | None = None,
    generated_from: datetime | None = None,
    generated_to: datetime | None = None,
    is_current: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PublicationHistoryResponse:
    items, total = _run(
        request,
        lambda: service.history(
            actor=actor,
            scope_type=scope_type,
            facility_id=facility_id,
            station_id=station_id,
            connector_id=connector_id,
            model_name=model_name,
            model_version=model_version,
            generated_from=generated_from,
            generated_to=generated_to,
            is_current=is_current,
            limit=limit,
            offset=offset,
        ),
    )
    technical = service.can_read_technical(actor)
    return PublicationHistoryResponse(
        items=[_technical_summary(item, technical_metadata=technical) for item in items],
        limit=limit,
        offset=offset,
        total=total,
    )


@router.get(
    "/weekly-occupancy-publications/current",
    response_model=CurrentPublicationResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
    summary="Retrieve the current publication for one canonical scope",
)
def current_weekly_occupancy_publication(
    request: Request,
    service: Annotated[PredictionService, Depends(prediction_service)],
    actor: Annotated[User, Depends(current_user)],
    scope_type: PredictionScopeType,
    facility_id: UUID,
    station_id: UUID | None = None,
    connector_id: UUID | None = None,
    include_profile: bool = False,
) -> CurrentPublicationResponse:
    result = _run(
        request,
        lambda: service.current(
            _scope(scope_type, facility_id, station_id, connector_id), actor=actor
        ),
    )
    summary = _technical_summary(result, technical_metadata=service.can_read_technical(actor))
    data = summary.model_dump()
    if include_profile:
        _, buckets = _run(request, lambda: service.profile(result.publication.id, actor=actor))
        data["buckets"] = [_bucket(item) for item in buckets]
    return CurrentPublicationResponse.model_validate(data)


@router.get(
    "/weekly-occupancy-publications/{publication_id}",
    response_model=PublicationSummaryResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
    summary="Retrieve one weekly occupancy publication",
)
def retrieve_weekly_occupancy_publication(
    publication_id: UUID,
    request: Request,
    service: Annotated[PredictionService, Depends(prediction_service)],
    actor: Annotated[User, Depends(current_user)],
) -> PublicationSummaryResponse:
    result = _run(request, lambda: service.get(publication_id, actor=actor))
    return _technical_summary(result, technical_metadata=service.can_read_technical(actor))


@router.get(
    "/weekly-occupancy-publications/{publication_id}/profile",
    response_model=PublicationProfileResponse,
    responses=ERRORS,
    summary="Retrieve the complete canonically ordered 168-bucket profile",
)
def retrieve_weekly_occupancy_profile(
    publication_id: UUID,
    request: Request,
    service: Annotated[PredictionService, Depends(prediction_service)],
    actor: Annotated[User, Depends(current_user)],
) -> PublicationProfileResponse:
    result, buckets = _run(request, lambda: service.profile(publication_id, actor=actor))
    return _profile(result.publication, buckets)


@router.get(
    "/weekly-occupancy/point",
    response_model=PredictionPointResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
    summary="Retrieve one recurring weekly occupancy bucket",
    description=(
        "Provide either local day_of_week plus hour_of_day, or one concrete timestamp "
        "with an explicit offset. The result is a recurring pattern, not a guarantee."
    ),
)
def weekly_occupancy_point(
    request: Request,
    service: Annotated[PredictionService, Depends(prediction_service)],
    actor: Annotated[User, Depends(current_user)],
    scope_type: PredictionScopeType,
    facility_id: UUID,
    station_id: UUID | None = None,
    connector_id: UUID | None = None,
    day_of_week: Weekday | None = None,
    hour_of_day: Annotated[int | None, Query(ge=0, le=23)] = None,
    timestamp: datetime | None = None,
) -> PredictionPointResponse:
    result: PointResult = _run(
        request,
        lambda: service.point(
            scope=_scope(scope_type, facility_id, station_id, connector_id),
            actor=actor,
            day_of_week=day_of_week,
            hour_of_day=hour_of_day,
            requested_timestamp=timestamp,
        ),
    )
    return PredictionPointResponse(
        scope=PredictionScopeResponse(**result.scope.canonical()),
        day_of_week=result.day_of_week,
        hour_of_day=result.hour_of_day,
        timezone=result.timezone,
        expected_occupancy_rate=result.expected_occupancy_rate,
        expected_availability_rate=1.0 - result.expected_occupancy_rate,
        publication_id=result.publication_id if result.technical_metadata_visible else None,
        accepted_at=(
            _utc_timestamp(result.accepted_at) if result.technical_metadata_visible else None
        ),
    )


def _recommendation_response(result: RecommendationResult) -> ConnectorRecommendationResponse:
    request_time = RecommendationRequestTime(
        input_type=result.input_type,
        timestamp=result.timestamp if result.input_type == "TIMESTAMP" else None,
        day_of_week=result.day_of_week if result.input_type != "TIMESTAMP" else None,
        hour_of_day=result.hour_of_day if result.input_type != "TIMESTAMP" else None,
    )
    resolved = None
    if result.shared_timezone is not None:
        if result.shared_day_of_week is None or result.shared_hour_of_day is None:
            raise PredictionPersistenceError(
                "Station recommendation resolved-time metadata is inconsistent."
            )
        resolved = ResolvedRecommendationTime(
            day_of_week=result.shared_day_of_week,
            hour_of_day=result.shared_hour_of_day,
            timezone=result.shared_timezone,
        )
    return ConnectorRecommendationResponse(
        request_time=request_time,
        resolved_time=resolved,
        items=[
            ConnectorRecommendationItem(
                rank=result.offset + index + 1,
                facility_id=item.facility_id,
                station_id=item.station_id,
                connector_id=item.connector_id,
                resolved_time=ResolvedRecommendationTime(
                    day_of_week=item.day_of_week,
                    hour_of_day=item.hour_of_day,
                    timezone=item.timezone,
                ),
                facility_status=item.facility_status,
                station_status=item.station_status,
                connector_status=item.connector_status,
                expected_occupancy_rate=item.expected_occupancy_rate,
                expected_availability_rate=item.expected_availability_rate,
            )
            for index, item in enumerate(result.items)
        ],
        limit=result.limit,
        offset=result.offset,
        total=result.total,
    )


@router.get(
    "/weekly-occupancy/recommendations/stations/{station_id}/connectors",
    response_model=ConnectorRecommendationResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
    summary="Rank eligible Connectors at one Station",
    description=(
        "All candidates belong to one Facility, so a shared resolved local time is returned "
        "when their current publications use that same Facility timezone."
    ),
)
def recommend_station_connectors(
    station_id: UUID,
    request: Request,
    service: Annotated[PredictionService, Depends(prediction_service)],
    actor: Annotated[User, Depends(current_user)],
    day_of_week: Weekday | None = None,
    hour_of_day: Annotated[int | None, Query(ge=0, le=23)] = None,
    timestamp: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConnectorRecommendationResponse:
    result = _run(
        request,
        lambda: service.recommend_connectors(
            actor=actor,
            day_of_week=day_of_week,
            hour_of_day=hour_of_day,
            requested_timestamp=timestamp,
            facility_id=None,
            station_id=station_id,
            limit=limit,
            offset=offset,
            station_specific=True,
        ),
    )
    return _recommendation_response(result)


@router.get(
    "/weekly-occupancy/recommendations/connectors",
    response_model=ConnectorRecommendationResponse,
    response_model_exclude_none=True,
    responses=ERRORS,
    summary="Rank eligible Connectors across infrastructure",
    description=(
        "For timestamp input, one absolute instant is resolved independently per candidate "
        "Facility timezone. For weekday/hour input, local civil time is interpreted independently "
        "per Facility and may denote different absolute instants. Resolved time is item-specific."
    ),
)
def recommend_connectors(
    request: Request,
    service: Annotated[PredictionService, Depends(prediction_service)],
    actor: Annotated[User, Depends(current_user)],
    day_of_week: Weekday | None = None,
    hour_of_day: Annotated[int | None, Query(ge=0, le=23)] = None,
    timestamp: datetime | None = None,
    facility_id: UUID | None = None,
    station_id: UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConnectorRecommendationResponse:
    result = _run(
        request,
        lambda: service.recommend_connectors(
            actor=actor,
            day_of_week=day_of_week,
            hour_of_day=hour_of_day,
            requested_timestamp=timestamp,
            facility_id=facility_id,
            station_id=station_id,
            limit=limit,
            offset=offset,
        ),
    )
    return _recommendation_response(result)
