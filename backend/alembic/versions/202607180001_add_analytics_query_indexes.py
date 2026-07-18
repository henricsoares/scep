"""add analytics query indexes

Revision ID: 202607180001
Revises: 202607170001
Create Date: 2026-07-18 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "202607180001"
down_revision: str | None = "202607170001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_charging_sessions_connector_started",
        "charging_sessions",
        ["connector_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_charging_sessions_connector_started", table_name="charging_sessions")
