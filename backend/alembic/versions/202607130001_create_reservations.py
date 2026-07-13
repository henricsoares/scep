"""create vehicles and reservations

Revision ID: 202607130001
Revises: 202607110001
Create Date: 2026-07-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607130001"
down_revision: str | None = "202607110001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(display_name)) > 0", name="ck_vehicles_display_name"),
        sa.CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_vehicles_status"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "owner_id", name="uq_vehicles_id_owner_id"),
    )
    op.create_index("ix_vehicles_owner_id", "vehicles", ["owner_id"])
    op.create_index("ix_vehicles_owner_status", "vehicles", ["owner_id", "status"])
    op.create_table(
        "reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("vehicle_id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("late_cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("no_show_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('CONFIRMED', 'ACTIVE', 'COMPLETED', 'CANCELLED', "
            "'LATE_CANCELLED', 'NO_SHOW')",
            name="ck_reservations_status",
        ),
        sa.CheckConstraint("start_at < end_at", name="ck_reservations_interval"),
        sa.CheckConstraint(
            "end_at - start_at >= INTERVAL '15 minutes' AND "
            "end_at - start_at <= INTERVAL '24 hours'",
            name="ck_reservations_duration",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"]),
        sa.ForeignKeyConstraint(
            ["vehicle_id", "owner_id"], ["vehicles.id", "vehicles.owner_id"],
            name="fk_reservations_vehicle_owner",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_reservations_owner_created", "reservations", ["owner_id", "created_at"])
    op.create_index(
        "ix_reservations_vehicle_interval", "reservations", ["vehicle_id", "start_at", "end_at"]
    )
    op.create_index(
        "ix_reservations_connector_interval", "reservations", ["connector_id", "start_at", "end_at"]
    )
    op.create_index("ix_reservations_status_start", "reservations", ["status", "start_at"])
    op.execute(
        "ALTER TABLE reservations ADD CONSTRAINT reservations_connector_no_overlap "
        "EXCLUDE USING gist (connector_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&) "
        "WHERE (status IN ('CONFIRMED', 'ACTIVE'))"
    )
    op.execute(
        "ALTER TABLE reservations ADD CONSTRAINT reservations_vehicle_no_overlap "
        "EXCLUDE USING gist (vehicle_id WITH =, tstzrange(start_at, end_at, '[)') WITH &&) "
        "WHERE (status IN ('CONFIRMED', 'ACTIVE'))"
    )


def downgrade() -> None:
    op.drop_index("ix_reservations_status_start", table_name="reservations")
    op.drop_index("ix_reservations_connector_interval", table_name="reservations")
    op.drop_index("ix_reservations_vehicle_interval", table_name="reservations")
    op.drop_index("ix_reservations_owner_created", table_name="reservations")
    op.drop_table("reservations")
    op.drop_index("ix_vehicles_owner_status", table_name="vehicles")
    op.drop_index("ix_vehicles_owner_id", table_name="vehicles")
    op.drop_table("vehicles")
