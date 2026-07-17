from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.events.domain import DeliveryStatus, EventType
from app.modules.events.infrastructure import DomainEventModel, EventDeliveryModel
from app.modules.identity.api.dependencies import require_admin
from app.modules.identity.domain.user import User

router = APIRouter(prefix="/domain-events", tags=["Domain Events"])


class EventDeliveryResponse(BaseModel):
    id: UUID
    event_id: UUID
    consumer: str
    status: DeliveryStatus
    attempts: int
    last_attempt_at: datetime | None
    delivered_at: datetime | None
    last_error: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DomainEventResponse(BaseModel):
    id: UUID
    event_type: EventType = Field(examples=[EventType.RESERVATION_CREATED])
    event_version: int = Field(examples=[1])
    aggregate_id: UUID
    aggregate_type: str
    producer_module: str
    occurred_at: datetime
    recorded_at: datetime
    correlation_id: UUID | None
    causation_id: UUID | None
    payload: dict[str, Any]
    metadata: dict[str, Any]
    created_at: datetime
    deliveries: list[EventDeliveryResponse]
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"event_type": item.value, "event_version": 1} for item in EventType]
        }
    )


def _response(item: DomainEventModel) -> DomainEventResponse:
    return DomainEventResponse(
        id=item.id,
        event_type=item.event_type,
        event_version=item.event_version,
        aggregate_id=item.aggregate_id,
        aggregate_type=item.aggregate_type,
        producer_module=item.producer_module,
        occurred_at=item.occurred_at,
        recorded_at=item.recorded_at,
        correlation_id=item.correlation_id,
        causation_id=item.causation_id,
        payload=item.payload,
        metadata=item.event_metadata,
        created_at=item.created_at,
        deliveries=[EventDeliveryResponse.model_validate(d) for d in item.deliveries],
    )


@router.get(
    "",
    response_model=list[DomainEventResponse],
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Platform Administrator required"},
    },
)
def list_events(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    event_type: str | None = None,
    aggregate_type: str | None = None,
    aggregate_id: UUID | None = None,
    producer_module: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    consumer: str | None = None,
    delivery_status: DeliveryStatus | None = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[DomainEventResponse]:
    stmt = select(DomainEventModel)
    for value, column in (
        (event_type, DomainEventModel.event_type),
        (aggregate_type, DomainEventModel.aggregate_type),
        (aggregate_id, DomainEventModel.aggregate_id),
        (producer_module, DomainEventModel.producer_module),
    ):
        if value is not None:
            stmt = stmt.where(column == value)
    if occurred_from is not None:
        stmt = stmt.where(DomainEventModel.occurred_at >= occurred_from)
    if occurred_to is not None:
        stmt = stmt.where(DomainEventModel.occurred_at <= occurred_to)
    if consumer is not None or delivery_status is not None:
        stmt = stmt.join(EventDeliveryModel)
        if consumer is not None:
            stmt = stmt.where(EventDeliveryModel.consumer == consumer)
        if delivery_status is not None:
            stmt = stmt.where(EventDeliveryModel.status == delivery_status.value)
    items = (
        db.scalars(
            stmt.order_by(DomainEventModel.occurred_at.desc(), DomainEventModel.id.desc())
            .offset(offset)
            .limit(limit)
        )
        .unique()
        .all()
    )
    return [_response(item) for item in items]


@router.get(
    "/{eventId}",
    response_model=DomainEventResponse,
    responses={
        401: {"description": "Unauthorized"},
        403: {"description": "Platform Administrator required"},
        404: {"description": "Domain Event not found"},
    },
)
def get_event(
    eventId: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> DomainEventResponse:
    item = db.get(DomainEventModel, eventId)
    if item is None:
        raise HTTPException(status_code=404, detail="domain event not found")
    return _response(item)
