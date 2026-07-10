from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class ChargingStationModel(Base):
    __tablename__ = "charging_stations"
    __table_args__ = (
        UniqueConstraint("serial_number", name="uq_charging_stations_serial_number"),
        Index("ix_charging_stations_facility_id", "facility_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    facility_id: Mapped[UUID] = mapped_column(ForeignKey("facilities.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    serial_number: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    maximum_power_kw: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    connectors: Mapped[list["ConnectorModel"]] = relationship(
        back_populates="station", lazy="selectin"
    )


class ConnectorModel(Base):
    __tablename__ = "connectors"
    __table_args__ = (
        Index("ix_connectors_charging_station_id", "charging_station_id"),
        Index("ix_connectors_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    charging_station_id: Mapped[UUID] = mapped_column(
        ForeignKey("charging_stations.id"), nullable=False
    )
    connector_type: Mapped[str] = mapped_column(String(64), nullable=False)
    maximum_power_kw: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    station: Mapped[ChargingStationModel] = relationship(back_populates="connectors")
