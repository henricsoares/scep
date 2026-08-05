from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    case,
    func,
    select,
    text,
)
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.infrastructure.database import Base
from app.modules.prediction.domain import PredictionScope, Weekday


class WeeklyOccupancyPredictionPublicationModel(Base):
    __tablename__ = "weekly_occupancy_prediction_publications"
    __table_args__ = (
        CheckConstraint(
            "prediction_type = 'WEEKLY_OCCUPANCY'",
            name="ck_prediction_publications_type",
        ),
        CheckConstraint("cycle = 'WEEKLY'", name="ck_prediction_publications_cycle"),
        CheckConstraint("granularity = 'HOUR'", name="ck_prediction_publications_granularity"),
        CheckConstraint(
            "contract_version = '1.0'", name="ck_prediction_publications_contract_version"
        ),
        CheckConstraint(
            "(scope_type = 'FACILITY' AND station_id IS NULL AND connector_id IS NULL) OR "
            "(scope_type = 'STATION' AND station_id IS NOT NULL AND connector_id IS NULL) OR "
            "(scope_type = 'CONNECTOR' AND station_id IS NOT NULL AND connector_id IS NOT NULL)",
            name="ck_prediction_publications_scope_shape",
        ),
        CheckConstraint(
            "(training_data_from IS NULL AND training_data_to IS NULL) OR "
            "(training_data_from IS NOT NULL AND training_data_to IS NOT NULL "
            "AND training_data_from < training_data_to)",
            name="ck_prediction_publications_training_window",
        ),
        CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 = lower(content_sha256)",
            name="ck_prediction_publications_sha256",
        ),
        UniqueConstraint("id", "scope_key", name="uq_prediction_publications_id_scope"),
        UniqueConstraint(
            "publisher_subject_id",
            "external_run_id",
            "scope_key",
            name="uq_prediction_publications_idempotency",
        ),
        Index(
            "ix_prediction_publications_scope_accepted",
            "scope_key",
            "accepted_at",
        ),
        Index(
            "ix_prediction_publications_scope_generated",
            "scope_key",
            "generated_at",
        ),
        Index(
            "ix_prediction_publications_model",
            "model_name",
            "model_version",
        ),
        Index("ix_prediction_publications_generated_at", "generated_at"),
        Index("ix_prediction_publications_dataset_export", "dataset_export_id"),
        Index(
            "ix_prediction_publications_publisher_run",
            "publisher_subject_id",
            "external_run_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    prediction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    cycle: Mapped[str] = mapped_column(String(16), nullable=False)
    granularity: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(160), nullable=False)
    facility_id: Mapped[UUID] = mapped_column(
        ForeignKey("facilities.id", ondelete="RESTRICT"), nullable=False
    )
    station_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("charging_stations.id", ondelete="RESTRICT")
    )
    connector_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("connectors.id", ondelete="RESTRICT")
    )
    timezone: Mapped[str] = mapped_column(String(128), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(16), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False)
    external_run_id: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    publisher_subject_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    dataset_export_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("dataset_exports.id", ondelete="RESTRICT")
    )
    training_data_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_data_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_content: Mapped[str] = mapped_column(Text, nullable=False)


class WeeklyOccupancyPredictionBucketModel(Base):
    __tablename__ = "weekly_occupancy_prediction_buckets"
    __table_args__ = (
        CheckConstraint(
            "day_of_week IN "
            "('MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY')",
            name="ck_prediction_buckets_weekday",
        ),
        CheckConstraint(
            "hour_of_day >= 0 AND hour_of_day <= 23",
            name="ck_prediction_buckets_hour",
        ),
        CheckConstraint(
            "expected_occupancy_rate >= 0 AND expected_occupancy_rate <= 1",
            name="ck_prediction_buckets_rate",
        ),
        Index(
            "ix_prediction_buckets_publication_lookup",
            "publication_id",
            "day_of_week",
            "hour_of_day",
        ),
    )

    publication_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "weekly_occupancy_prediction_publications.id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )
    day_of_week: Mapped[str] = mapped_column(String(16), primary_key=True)
    hour_of_day: Mapped[int] = mapped_column(Integer, primary_key=True)
    expected_occupancy_rate: Mapped[float] = mapped_column(Float, nullable=False)


class WeeklyOccupancyPredictionCurrentModel(Base):
    __tablename__ = "weekly_occupancy_prediction_current"
    __table_args__ = (
        CheckConstraint(
            "(scope_type = 'FACILITY' AND station_id IS NULL AND connector_id IS NULL) OR "
            "(scope_type = 'STATION' AND station_id IS NOT NULL AND connector_id IS NULL) OR "
            "(scope_type = 'CONNECTOR' AND station_id IS NOT NULL AND connector_id IS NOT NULL)",
            name="ck_prediction_current_scope_shape",
        ),
        ForeignKeyConstraint(
            ["publication_id", "scope_key"],
            [
                "weekly_occupancy_prediction_publications.id",
                "weekly_occupancy_prediction_publications.scope_key",
            ],
            ondelete="RESTRICT",
            name="fk_prediction_current_publication_scope",
        ),
        UniqueConstraint("publication_id", name="uq_prediction_current_publication"),
        Index(
            "ix_prediction_current_hierarchy",
            "scope_type",
            "facility_id",
            "station_id",
            "connector_id",
        ),
    )

    scope_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    scope_type: Mapped[str] = mapped_column(String(16), nullable=False)
    facility_id: Mapped[UUID] = mapped_column(
        ForeignKey("facilities.id", ondelete="RESTRICT"), nullable=False
    )
    station_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("charging_stations.id", ondelete="RESTRICT")
    )
    connector_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("connectors.id", ondelete="RESTRICT")
    )
    publication_id: Mapped[UUID] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


_WEEKDAY_ORDER = case(
    {day.value: index for index, day in enumerate(Weekday)},
    value=WeeklyOccupancyPredictionBucketModel.day_of_week,
)


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def lock_scope(self, scope_key: str) -> None:
        if self.session.get_bind().dialect.name == "postgresql":
            self.session.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:scope_key, 0))"),
                {"scope_key": scope_key},
            )

    def find_idempotency(
        self, *, publisher_subject_id: UUID, external_run_id: str, scope_key: str
    ) -> WeeklyOccupancyPredictionPublicationModel | None:
        return self.session.scalar(
            select(WeeklyOccupancyPredictionPublicationModel).where(
                WeeklyOccupancyPredictionPublicationModel.publisher_subject_id
                == publisher_subject_id,
                WeeklyOccupancyPredictionPublicationModel.external_run_id == external_run_id,
                WeeklyOccupancyPredictionPublicationModel.scope_key == scope_key,
            )
        )

    def add_publication(
        self,
        publication: WeeklyOccupancyPredictionPublicationModel,
        buckets: list[WeeklyOccupancyPredictionBucketModel],
    ) -> None:
        self.session.add(publication)
        self.session.flush()
        self.session.add_all(buckets)
        self.session.flush()

    def get(self, publication_id: UUID) -> WeeklyOccupancyPredictionPublicationModel | None:
        return self.session.get(WeeklyOccupancyPredictionPublicationModel, publication_id)

    def buckets(self, publication_id: UUID) -> list[WeeklyOccupancyPredictionBucketModel]:
        return list(
            self.session.scalars(
                select(WeeklyOccupancyPredictionBucketModel)
                .where(WeeklyOccupancyPredictionBucketModel.publication_id == publication_id)
                .order_by(_WEEKDAY_ORDER, WeeklyOccupancyPredictionBucketModel.hour_of_day)
            )
        )

    def current_reference(
        self, scope_key: str, *, for_update: bool = False
    ) -> WeeklyOccupancyPredictionCurrentModel | None:
        statement = select(WeeklyOccupancyPredictionCurrentModel).where(
            WeeklyOccupancyPredictionCurrentModel.scope_key == scope_key
        )
        if for_update:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def set_current(
        self,
        *,
        scope: PredictionScope,
        publication_id: UUID,
        accepted_at: datetime,
    ) -> None:
        current = self.current_reference(scope.key, for_update=True)
        if current is None:
            self.session.add(
                WeeklyOccupancyPredictionCurrentModel(
                    scope_key=scope.key,
                    scope_type=scope.scope_type.value,
                    facility_id=scope.facility_id,
                    station_id=scope.station_id,
                    connector_id=scope.connector_id,
                    publication_id=publication_id,
                    updated_at=accepted_at,
                )
            )
        else:
            current.publication_id = publication_id
            current.updated_at = accepted_at
        self.session.flush()

    def is_current(self, publication_id: UUID) -> bool:
        return (
            self.session.scalar(
                select(WeeklyOccupancyPredictionCurrentModel.scope_key).where(
                    WeeklyOccupancyPredictionCurrentModel.publication_id == publication_id
                )
            )
            is not None
        )

    def current_publication(
        self, scope_key: str
    ) -> WeeklyOccupancyPredictionPublicationModel | None:
        return self.session.scalar(
            select(WeeklyOccupancyPredictionPublicationModel)
            .join(
                WeeklyOccupancyPredictionCurrentModel,
                WeeklyOccupancyPredictionCurrentModel.publication_id
                == WeeklyOccupancyPredictionPublicationModel.id,
            )
            .where(WeeklyOccupancyPredictionCurrentModel.scope_key == scope_key)
        )

    def current_bucket(self, *, scope_key: str, day_of_week: Weekday, hour_of_day: int) -> (
        tuple[
            WeeklyOccupancyPredictionPublicationModel,
            WeeklyOccupancyPredictionBucketModel,
        ]
        | None
    ):
        row = self.session.execute(
            select(
                WeeklyOccupancyPredictionPublicationModel,
                WeeklyOccupancyPredictionBucketModel,
            )
            .join(
                WeeklyOccupancyPredictionCurrentModel,
                WeeklyOccupancyPredictionCurrentModel.publication_id
                == WeeklyOccupancyPredictionPublicationModel.id,
            )
            .join(
                WeeklyOccupancyPredictionBucketModel,
                WeeklyOccupancyPredictionBucketModel.publication_id
                == WeeklyOccupancyPredictionPublicationModel.id,
            )
            .where(
                WeeklyOccupancyPredictionCurrentModel.scope_key == scope_key,
                WeeklyOccupancyPredictionBucketModel.day_of_week == day_of_week.value,
                WeeklyOccupancyPredictionBucketModel.hour_of_day == hour_of_day,
            )
        ).one_or_none()
        return None if row is None else (row[0], row[1])

    def list(
        self,
        *,
        scope_type: str | None = None,
        facility_id: UUID | None = None,
        station_id: UUID | None = None,
        connector_id: UUID | None = None,
        model_name: str | None = None,
        model_version: str | None = None,
        generated_from: datetime | None = None,
        generated_to: datetime | None = None,
        is_current: bool | None = None,
        visible_facility_ids: tuple[UUID, ...] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[WeeklyOccupancyPredictionPublicationModel, bool]], int]:
        publication = WeeklyOccupancyPredictionPublicationModel
        current = WeeklyOccupancyPredictionCurrentModel
        conditions = []
        if scope_type is not None:
            conditions.append(publication.scope_type == scope_type)
        if facility_id is not None:
            conditions.append(publication.facility_id == facility_id)
        if station_id is not None:
            conditions.append(publication.station_id == station_id)
        if connector_id is not None:
            conditions.append(publication.connector_id == connector_id)
        if model_name is not None:
            conditions.append(publication.model_name == model_name)
        if model_version is not None:
            conditions.append(publication.model_version == model_version)
        if generated_from is not None:
            conditions.append(publication.generated_at >= generated_from)
        if generated_to is not None:
            conditions.append(publication.generated_at < generated_to)
        if visible_facility_ids is not None:
            conditions.append(publication.facility_id.in_(visible_facility_ids))
        current_match = current.publication_id.is_not(None)
        statement = (
            select(publication, current_match)
            .outerjoin(current, current.publication_id == publication.id)
            .where(*conditions)
        )
        count_statement = (
            select(func.count())
            .select_from(publication)
            .outerjoin(current, current.publication_id == publication.id)
            .where(*conditions)
        )
        if is_current is not None:
            current_condition = (
                current.publication_id.is_not(None)
                if is_current
                else current.publication_id.is_(None)
            )
            statement = statement.where(current_condition)
            count_statement = count_statement.where(current_condition)
        total = int(self.session.scalar(count_statement) or 0)
        rows = self.session.execute(
            statement.order_by(publication.accepted_at.desc(), publication.id)
            .offset(offset)
            .limit(limit)
        )
        return [(row[0], bool(row[1])) for row in rows], total
