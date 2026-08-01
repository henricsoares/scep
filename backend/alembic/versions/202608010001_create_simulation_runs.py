"""create SimulationRun context, receipts, and operational provenance

Revision ID: 202608010001
Revises: 202607210001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608010001"
down_revision: str | None = "202607210001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "simulation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("logical_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("logical_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accepted_simulated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credential_hash", sa.String(255), nullable=True),
        sa.Column("external_scenario_id", sa.String(255), nullable=True),
        sa.Column("external_scenario_version", sa.String(128), nullable=True),
        sa.Column("scenario_sha256", sa.String(64), nullable=True),
        sa.Column("simulator_version", sa.String(128), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('DRAFT','RUNNING','COMPLETED','CANCELLED')",
            name="ck_simulation_runs_status",
        ),
        sa.CheckConstraint(
            "logical_start_at < logical_end_at", name="ck_simulation_runs_logical_window"
        ),
        sa.CheckConstraint(
            "last_accepted_simulated_at IS NULL OR "
            "(last_accepted_simulated_at >= logical_start_at AND "
            "last_accepted_simulated_at <= logical_end_at)",
            name="ck_simulation_runs_last_accepted_window",
        ),
        sa.CheckConstraint(
            "scenario_sha256 IS NULL OR "
            "(length(scenario_sha256) = 64 AND scenario_sha256 = lower(scenario_sha256))",
            name="ck_simulation_runs_scenario_sha256",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_simulation_runs_status_created", "simulation_runs", ["status", "created_at"]
    )
    op.create_table(
        "simulation_run_facilities",
        sa.Column("simulation_run_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("simulation_run_id", "facility_id"),
    )
    op.create_table(
        "simulation_run_evdrivers",
        sa.Column("simulation_run_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("simulation_run_id", "user_id"),
    )
    op.create_table(
        "simulation_event_receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("simulation_run_id", sa.Uuid(), nullable=False),
        sa.Column("simulation_event_id", sa.Uuid(), nullable=False),
        sa.Column("operation", sa.String(64), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("simulated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("request_sha256", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=True),
        sa.Column("resource_id", sa.Uuid(), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "response_status >= 200 AND response_status < 300", name="ck_receipt_status"
        ),
        sa.CheckConstraint("length(request_sha256) = 64", name="ck_receipt_request_sha256"),
        sa.ForeignKeyConstraint(["simulation_run_id"], ["simulation_runs.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "simulation_run_id",
            "operation",
            "simulation_event_id",
            name="uq_simulation_event_receipts_logical_key",
        ),
    )
    op.create_index(
        "ix_simulation_event_receipts_run_time",
        "simulation_event_receipts",
        ["simulation_run_id", "simulated_at"],
    )
    op.add_column("reservations", sa.Column("simulation_run_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_reservations_simulation_run",
        "reservations",
        "simulation_runs",
        ["simulation_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_reservations_simulation_run_start",
        "reservations",
        ["simulation_run_id", "start_at"],
    )
    op.add_column("charging_sessions", sa.Column("simulation_run_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_charging_sessions_simulation_run",
        "charging_sessions",
        "simulation_runs",
        ["simulation_run_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_charging_sessions_simulation_run_status",
        "charging_sessions",
        ["simulation_run_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_charging_sessions_simulation_run_status", table_name="charging_sessions")
    op.drop_constraint(
        "fk_charging_sessions_simulation_run", "charging_sessions", type_="foreignkey"
    )
    op.drop_column("charging_sessions", "simulation_run_id")
    op.drop_index("ix_reservations_simulation_run_start", table_name="reservations")
    op.drop_constraint("fk_reservations_simulation_run", "reservations", type_="foreignkey")
    op.drop_column("reservations", "simulation_run_id")
    op.drop_index("ix_simulation_event_receipts_run_time", table_name="simulation_event_receipts")
    op.drop_table("simulation_event_receipts")
    op.drop_table("simulation_run_evdrivers")
    op.drop_table("simulation_run_facilities")
    op.drop_index("ix_simulation_runs_status_created", table_name="simulation_runs")
    op.drop_table("simulation_runs")
