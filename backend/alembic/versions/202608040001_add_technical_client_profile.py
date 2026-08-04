"""add the closed Technical Client profile used by the AI research environment

Revision ID: 202608040001
Revises: 202608010001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608040001"
down_revision: str | None = "202608010001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("technical_profile", sa.String(64), nullable=True))
    op.create_check_constraint(
        "ck_users_technical_profile",
        "users",
        "(account_type = 'Human' AND technical_profile IS NULL) OR "
        "(account_type = 'TechnicalClient' AND "
        "(technical_profile IS NULL OR technical_profile = 'AIResearchEnvironment'))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_users_technical_profile", "users", type_="check")
    op.drop_column("users", "technical_profile")
