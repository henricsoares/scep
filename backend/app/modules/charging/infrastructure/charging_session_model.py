from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class ChargingSessionModel(Base):
    __tablename__ = "charging_sessions"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'COMPLETED')", name="ck_charging_sessions_status"),
        CheckConstraint(
            "(status = 'ACTIVE' AND ended_at IS NULL) OR "
            "(status = 'COMPLETED' AND ended_at IS NOT NULL)",
            name="ck_charging_sessions_ended_at",
        ),
        Index("uq_charging_sessions_reservation", "reservation_id", unique=True),
        Index(
            "uq_charging_sessions_active_vehicle",
            "vehicle_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index(
            "uq_charging_sessions_active_connector",
            "connector_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
        Index("ix_charging_sessions_owner_created", "owner_id", "created_at"),
        Index("ix_charging_sessions_status_started", "status", "started_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    reservation_id: Mapped[UUID] = mapped_column(ForeignKey("reservations.id"), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    vehicle_id: Mapped[UUID] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    connector_id: Mapped[UUID] = mapped_column(ForeignKey("connectors.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
