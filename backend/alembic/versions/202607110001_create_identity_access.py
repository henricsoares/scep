"""create identity and access tables

Revision ID: 202607110001
Revises: 202607100001
Create Date: 2026-07-11 00:00:00.000000
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "202607110001"
down_revision: str | None = "202607100001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
ROLES = ["PlatformAdministrator", "FacilityOperator", "EVDriver", "Researcher", "DataScientist"]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("account_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "account_type IN ('Human', 'TechnicalClient')", name="ck_users_account_type"
        ),
        sa.CheckConstraint("status IN ('Active', 'Inactive')", name="ck_users_status"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_status", "users", ["status"])
    op.create_index("ix_users_account_type", "users", ["account_type"])
    op.create_table(
        "roles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_roles_name"),
    )
    role_table = sa.table("roles", sa.column("id", sa.Uuid()), sa.column("name", sa.String()))
    op.bulk_insert(role_table, [{"id": uuid4(), "name": r} for r in ROLES])
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
        sa.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
    )
    op.create_table(
        "user_facilities",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "facility_id"),
        sa.UniqueConstraint("user_id", "facility_id", name="uq_user_facilities_user_facility"),
    )
    op.create_index("ix_user_facilities_facility_id", "user_facilities", ["facility_id"])


def downgrade() -> None:
    op.drop_index("ix_user_facilities_facility_id", table_name="user_facilities")
    op.drop_table("user_facilities")
    op.drop_table("user_roles")
    op.drop_table("roles")
    op.drop_index("ix_users_account_type", table_name="users")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_table("users")
