"""initial empty migration

Revision ID: 202607070001
Revises:
Create Date: 2026-07-07 00:00:00.000000
"""
from collections.abc import Sequence

revision: str = "202607070001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
