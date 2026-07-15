"""create telemetry samples

Revision ID: 202607150001
Revises: 202607140001
Create Date: 2026-07-15 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607150001"
down_revision: str | None = "202607140001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telemetry_samples",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("sample_id", sa.String(255), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("power_kw", sa.Float(), nullable=True),
        sa.Column("energy_kwh", sa.Float(), nullable=True),
        sa.Column("state_of_charge_percent", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("source IN ('SIMULATOR', 'API_CLIENT')", name="ck_telemetry_source"),
        sa.CheckConstraint("power_kw IS NULL OR power_kw >= 0", name="ck_telemetry_power"),
        sa.CheckConstraint("energy_kwh IS NULL OR energy_kwh >= 0", name="ck_telemetry_energy"),
        sa.CheckConstraint(
            "state_of_charge_percent IS NULL OR "
            "(state_of_charge_percent >= 0 AND state_of_charge_percent <= 100)",
            name="ck_telemetry_soc",
        ),
        sa.CheckConstraint(
            "power_kw IS NOT NULL OR energy_kwh IS NOT NULL OR "
            "state_of_charge_percent IS NOT NULL",
            name="ck_telemetry_measurement_present",
        ),
        sa.CheckConstraint(
            "(power_kw IS NULL OR power_kw NOT IN ('Infinity', '-Infinity', 'NaN')) AND "
            "(energy_kwh IS NULL OR energy_kwh NOT IN ('Infinity', '-Infinity', 'NaN')) AND "
            "(state_of_charge_percent IS NULL OR "
            "state_of_charge_percent NOT IN ('Infinity', '-Infinity', 'NaN'))",
            name="ck_telemetry_finite",
        ),
        sa.ForeignKeyConstraint(["session_id"], ["charging_sessions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_telemetry_session_source_sample",
        "telemetry_samples",
        ["session_id", "source", "sample_id"],
        unique=True,
    )
    op.create_index(
        "ix_telemetry_session_recorded",
        "telemetry_samples",
        ["session_id", "recorded_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_telemetry_session_recorded", table_name="telemetry_samples")
    op.drop_index("uq_telemetry_session_source_sample", table_name="telemetry_samples")
    op.drop_table("telemetry_samples")
