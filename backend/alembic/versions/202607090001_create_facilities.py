"""create facilities table

Revision ID: 202607090001
Revises: 202607070001
Create Date: 2026-07-09 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607090001"
down_revision: str | None = "202607070001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "facilities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("facility_type", sa.String(length=64), nullable=False),
        sa.Column("timezone", sa.String(length=128), nullable=False),
        sa.Column("country", sa.String(length=128), nullable=False),
        sa.Column("city", sa.String(length=128), nullable=False),
        sa.Column("address", sa.String(length=512), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("operating_hours", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_facilities_name"),
    )


def downgrade() -> None:
    op.drop_table("facilities")
