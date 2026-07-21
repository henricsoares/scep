"""create Dataset Export metadata and lifecycle indexes

Revision ID: 202607210001
Revises: 202607180001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607210001"
down_revision: str | None = "202607180001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dataset_exports",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requested_by", sa.Uuid(), nullable=False),
        sa.Column("dataset_type", sa.String(64), nullable=False),
        sa.Column("export_profile", sa.String(32), nullable=False),
        sa.Column("format", sa.String(16), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("data_cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(64), nullable=True),
        sa.Column("failure_message", sa.String(512), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("data_file_sha256", sa.String(64), nullable=True),
        sa.Column("artifact_sha256", sa.String(64), nullable=True),
        sa.Column("artifact_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("artifact_storage_key", sa.String(255), nullable=True),
        sa.Column("artifact_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("artifact_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "dataset_type IN ('OPERATIONAL_CHARGING_SESSIONS','OPERATIONAL_TELEMETRY','ANALYTICAL_OCCUPANCY')",
            name="ck_dataset_exports_type",
        ),
        sa.CheckConstraint(
            "export_profile IN ('ADMINISTRATIVE','RESEARCH')",
            name="ck_dataset_exports_profile",
        ),
        sa.CheckConstraint("format IN ('CSV','PARQUET')", name="ck_dataset_exports_format"),
        sa.CheckConstraint(
            "status IN ('PENDING','PROCESSING','COMPLETED','FAILED')",
            name="ck_dataset_exports_status",
        ),
        sa.CheckConstraint(
            "failure_code IS NULL OR failure_code IN "
            "('ROW_LIMIT_EXCEEDED','ARTIFACT_SIZE_LIMIT_EXCEEDED','PROCESSING_TIMEOUT',"
            "'STORAGE_FAILURE','GENERATION_FAILURE','SNAPSHOT_LOST','ABANDONED_PROCESSING')",
            name="ck_dataset_exports_failure_code",
        ),
        sa.CheckConstraint(
            "(status = 'PENDING' AND started_at IS NULL AND data_cutoff_at IS NULL) OR "
            "(status = 'PROCESSING' AND started_at IS NOT NULL) OR "
            "(status = 'COMPLETED' AND completed_at IS NOT NULL AND artifact_storage_key IS NOT NULL) OR "
            "(status = 'FAILED' AND failed_at IS NOT NULL AND failure_code IS NOT NULL)",
            name="ck_dataset_exports_lifecycle",
        ),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dataset_exports_status", "dataset_exports", ["status"])
    op.create_index("ix_dataset_exports_requested_by", "dataset_exports", ["requested_by"])
    op.create_index("ix_dataset_exports_created_at", "dataset_exports", ["created_at"])
    op.create_index(
        "ix_dataset_exports_owner_created", "dataset_exports", ["requested_by", "created_at"]
    )
    op.create_index(
        "ix_dataset_exports_status_created", "dataset_exports", ["status", "created_at"]
    )
    op.create_index(
        "ix_dataset_exports_artifact_expires", "dataset_exports", ["artifact_expires_at"]
    )
    op.create_index(
        "ix_telemetry_recorded_received",
        "telemetry_samples",
        ["recorded_at", "received_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_telemetry_recorded_received", table_name="telemetry_samples")
    op.drop_index("ix_dataset_exports_artifact_expires", table_name="dataset_exports")
    op.drop_index("ix_dataset_exports_status_created", table_name="dataset_exports")
    op.drop_index("ix_dataset_exports_owner_created", table_name="dataset_exports")
    op.drop_index("ix_dataset_exports_created_at", table_name="dataset_exports")
    op.drop_index("ix_dataset_exports_requested_by", table_name="dataset_exports")
    op.drop_index("ix_dataset_exports_status", table_name="dataset_exports")
    op.drop_table("dataset_exports")
