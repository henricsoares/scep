"""create charging stations and connectors

Revision ID: 202607100001
Revises: 202607090001
Create Date: 2026-07-10 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

revision: str = "202607100001"
down_revision: str | None = "202607090001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    from alembic import op as alembic_op

    alembic_op.create_table(
        "charging_stations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=True),
        sa.Column("serial_number", sa.String(length=255), nullable=False),
        sa.Column("manufacturer", sa.String(length=255), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("maximum_power_kw", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("serial_number", name="uq_charging_stations_serial_number"),
    )
    alembic_op.create_index(
        "ix_charging_stations_facility_id", "charging_stations", ["facility_id"]
    )
    alembic_op.create_table(
        "connectors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("charging_station_id", sa.Uuid(), nullable=False),
        sa.Column("connector_type", sa.String(length=64), nullable=False),
        sa.Column("maximum_power_kw", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["charging_station_id"], ["charging_stations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    alembic_op.create_index(
        "ix_connectors_charging_station_id", "connectors", ["charging_station_id"]
    )
    alembic_op.create_index("ix_connectors_status", "connectors", ["status"])


def downgrade() -> None:
    from alembic import op as alembic_op

    alembic_op.drop_index("ix_connectors_status", table_name="connectors")
    alembic_op.drop_index("ix_connectors_charging_station_id", table_name="connectors")
    alembic_op.drop_table("connectors")
    alembic_op.drop_index("ix_charging_stations_facility_id", table_name="charging_stations")
    alembic_op.drop_table("charging_stations")
