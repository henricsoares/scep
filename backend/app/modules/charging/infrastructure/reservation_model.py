from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class VehicleModel(Base):
    __tablename__ = "vehicles"
    __table_args__ = (
        UniqueConstraint("id", "owner_id", name="uq_vehicles_id_owner_id"),
        CheckConstraint("length(trim(display_name)) > 0", name="ck_vehicles_display_name"),
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_vehicles_status"),
        Index("ix_vehicles_owner_id", "owner_id"),
        Index("ix_vehicles_owner_status", "owner_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ReservationModel(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["vehicle_id", "owner_id"],
            ["vehicles.id", "vehicles.owner_id"],
            name="fk_reservations_vehicle_owner",
        ),
        CheckConstraint(
            "status IN ('CONFIRMED', 'ACTIVE', 'COMPLETED', 'CANCELLED', "
            "'LATE_CANCELLED', 'NO_SHOW')",
            name="ck_reservations_status",
        ),
        CheckConstraint("start_at < end_at", name="ck_reservations_interval"),
        Index("ix_reservations_owner_created", "owner_id", "created_at"),
        Index("ix_reservations_vehicle_interval", "vehicle_id", "start_at", "end_at"),
        Index("ix_reservations_connector_interval", "connector_id", "start_at", "end_at"),
        Index("ix_reservations_status_start", "status", "start_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    vehicle_id: Mapped[UUID] = mapped_column(nullable=False)
    connector_id: Mapped[UUID] = mapped_column(ForeignKey("connectors.id"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    late_cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    no_show_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
