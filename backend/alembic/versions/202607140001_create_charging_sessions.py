"""create charging sessions

Revision ID: 202607140001
Revises: 202607130001
Create Date: 2026-07-14 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607140001"
down_revision: str | None = "202607130001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "charging_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("reservation_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status IN ('ACTIVE', 'COMPLETED')", name="ck_charging_sessions_status"),
        sa.CheckConstraint(
            "(status = 'ACTIVE' AND ended_at IS NULL) OR "
            "(status = 'COMPLETED' AND ended_at IS NOT NULL)",
            name="ck_charging_sessions_ended_at",
        ),
        sa.ForeignKeyConstraint(["reservation_id"], ["reservations.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"]),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_charging_sessions_reservation", "charging_sessions", ["reservation_id"], unique=True
    )
    op.create_index(
        "uq_charging_sessions_active_vehicle",
        "charging_sessions",
        ["vehicle_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "uq_charging_sessions_active_connector",
        "charging_sessions",
        ["connector_id"],
        unique=True,
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    op.create_index(
        "ix_charging_sessions_owner_created", "charging_sessions", ["owner_id", "created_at"]
    )
    op.create_index(
        "ix_charging_sessions_status_started", "charging_sessions", ["status", "started_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_charging_sessions_status_started", table_name="charging_sessions")
    op.drop_index("ix_charging_sessions_owner_created", table_name="charging_sessions")
    op.drop_index("uq_charging_sessions_active_connector", table_name="charging_sessions")
    op.drop_index("uq_charging_sessions_active_vehicle", table_name="charging_sessions")
    op.drop_index("uq_charging_sessions_reservation", table_name="charging_sessions")
    op.drop_table("charging_sessions")
