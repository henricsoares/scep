from __future__ import annotations

from builtins import list as list_type
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    func,
    select,
    update,
)
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.infrastructure.database import Base
from app.modules.datasets.domain import (
    CreateExport,
    DatasetType,
    ExportProfile,
    ExportStatus,
    FailureCode,
)


class DatasetExportModel(Base):
    __tablename__ = "dataset_exports"
    __table_args__ = (
        CheckConstraint(
            "dataset_type IN ('OPERATIONAL_CHARGING_SESSIONS',"
            "'OPERATIONAL_TELEMETRY','ANALYTICAL_OCCUPANCY')",
            name="ck_dataset_exports_type",
        ),
        CheckConstraint(
            "export_profile IN ('ADMINISTRATIVE','RESEARCH')",
            name="ck_dataset_exports_profile",
        ),
        CheckConstraint("format IN ('CSV','PARQUET')", name="ck_dataset_exports_format"),
        CheckConstraint(
            "status IN ('PENDING','PROCESSING','COMPLETED','FAILED')",
            name="ck_dataset_exports_status",
        ),
        CheckConstraint(
            "failure_code IS NULL OR failure_code IN "
            "('ROW_LIMIT_EXCEEDED','ARTIFACT_SIZE_LIMIT_EXCEEDED','PROCESSING_TIMEOUT',"
            "'STORAGE_FAILURE','GENERATION_FAILURE','SNAPSHOT_LOST','ABANDONED_PROCESSING')",
            name="ck_dataset_exports_failure_code",
        ),
        CheckConstraint(
            "(status = 'PENDING' AND started_at IS NULL AND data_cutoff_at IS NULL) OR "
            "(status = 'PROCESSING' AND started_at IS NOT NULL) OR "
            "(status = 'COMPLETED' AND completed_at IS NOT NULL "
            "AND artifact_storage_key IS NOT NULL) OR "
            "(status = 'FAILED' AND failed_at IS NOT NULL AND failure_code IS NOT NULL)",
            name="ck_dataset_exports_lifecycle",
        ),
        Index("ix_dataset_exports_status", "status"),
        Index("ix_dataset_exports_requested_by", "requested_by"),
        Index("ix_dataset_exports_created_at", "created_at"),
        Index("ix_dataset_exports_owner_created", "requested_by", "created_at"),
        Index("ix_dataset_exports_status_created", "status", "created_at"),
        Index("ix_dataset_exports_artifact_expires", "artifact_expires_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    requested_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    dataset_type: Mapped[str] = mapped_column(String(64), nullable=False)
    export_profile: Mapped[str] = mapped_column(String(32), nullable=False)
    format: Mapped[str] = mapped_column(String(16), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    data_cutoff_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_message: Mapped[str | None] = mapped_column(String(512))
    row_count: Mapped[int | None]
    data_file_sha256: Mapped[str | None] = mapped_column(String(64))
    artifact_sha256: Mapped[str | None] = mapped_column(String(64))
    artifact_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    artifact_storage_key: Mapped[str | None] = mapped_column(String(255))
    artifact_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    artifact_deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DatasetExportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, item: CreateExport) -> DatasetExportModel:
        model = DatasetExportModel(
            id=item.id,
            requested_by=item.requested_by,
            dataset_type=item.dataset_type.value,
            export_profile=item.export_profile.value,
            format=item.format.value,
            filters=item.filters.canonical(),
            status=ExportStatus.PENDING.value,
            schema_version="1.0.0",
            created_at=item.created_at,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model

    def get(self, export_id: UUID) -> DatasetExportModel | None:
        return self.session.get(DatasetExportModel, export_id)

    def count_pending(self) -> int:
        return int(
            self.session.scalar(
                select(func.count())
                .select_from(DatasetExportModel)
                .where(DatasetExportModel.status == ExportStatus.PENDING.value)
            )
            or 0
        )

    def list(
        self,
        *,
        requested_by: UUID | None = None,
        status: ExportStatus | None = None,
        dataset_type: DatasetType | None = None,
        export_profile: ExportProfile | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[DatasetExportModel], int]:
        conditions = []
        if requested_by:
            conditions.append(DatasetExportModel.requested_by == requested_by)
        if status:
            conditions.append(DatasetExportModel.status == status.value)
        if dataset_type:
            conditions.append(DatasetExportModel.dataset_type == dataset_type.value)
        if export_profile:
            conditions.append(DatasetExportModel.export_profile == export_profile.value)
        if created_from:
            conditions.append(DatasetExportModel.created_at >= created_from)
        if created_to:
            conditions.append(DatasetExportModel.created_at < created_to)
        base = select(DatasetExportModel).where(*conditions)
        total = int(
            self.session.scalar(
                select(func.count()).select_from(DatasetExportModel).where(*conditions)
            )
            or 0
        )
        items = list(
            self.session.scalars(
                base.order_by(DatasetExportModel.created_at.desc(), DatasetExportModel.id)
                .offset(offset)
                .limit(limit)
            )
        )
        return items, total

    def claim(self, export_id: UUID, started_at: datetime) -> bool:
        result = cast(
            CursorResult[Any],
            self.session.execute(
                update(DatasetExportModel)
                .where(
                    DatasetExportModel.id == export_id,
                    DatasetExportModel.status == ExportStatus.PENDING.value,
                )
                .values(status=ExportStatus.PROCESSING.value, started_at=started_at)
            ),
        )
        self.session.commit()
        return bool(result.rowcount)

    def set_cutoff(self, export_id: UUID, cutoff: datetime) -> None:
        self.session.execute(
            update(DatasetExportModel)
            .where(
                DatasetExportModel.id == export_id,
                DatasetExportModel.status == ExportStatus.PROCESSING.value,
                DatasetExportModel.data_cutoff_at.is_(None),
            )
            .values(data_cutoff_at=cutoff)
        )
        self.session.commit()

    def fail(self, export_id: UUID, code: FailureCode, message: str) -> None:
        self.session.execute(
            update(DatasetExportModel)
            .where(
                DatasetExportModel.id == export_id,
                DatasetExportModel.status == ExportStatus.PROCESSING.value,
            )
            .values(
                status=ExportStatus.FAILED.value,
                failed_at=datetime.now(UTC),
                failure_code=code.value,
                failure_message=message[:512],
                artifact_storage_key=None,
            )
        )
        self.session.commit()

    def recover_processing(self, older_than: datetime, *, snapshot_lost: bool) -> int:
        code = FailureCode.SNAPSHOT_LOST if snapshot_lost else FailureCode.ABANDONED_PROCESSING
        result = cast(
            CursorResult[Any],
            self.session.execute(
                update(DatasetExportModel)
                .where(
                    DatasetExportModel.status == ExportStatus.PROCESSING.value,
                    DatasetExportModel.started_at < older_than,
                )
                .values(
                    status=ExportStatus.FAILED.value,
                    failed_at=datetime.now(UTC),
                    failure_code=code.value,
                    failure_message="Processing could not be resumed safely.",
                )
            ),
        )
        self.session.commit()
        return int(result.rowcount)

    def expired(self, now: datetime) -> list_type[DatasetExportModel]:
        return list_type(
            self.session.scalars(
                select(DatasetExportModel).where(
                    DatasetExportModel.status == ExportStatus.COMPLETED.value,
                    DatasetExportModel.artifact_expires_at <= now,
                    DatasetExportModel.artifact_storage_key.is_not(None),
                    DatasetExportModel.artifact_deleted_at.is_(None),
                )
            )
        )

    def mark_artifact_deleted(self, export_id: UUID, deleted_at: datetime) -> None:
        model = self.get(export_id)
        if model is not None:
            model.artifact_deleted_at = deleted_at
            self.session.commit()


def retention_boundary(completed_at: datetime, days: int) -> datetime:
    return completed_at + timedelta(days=days)
