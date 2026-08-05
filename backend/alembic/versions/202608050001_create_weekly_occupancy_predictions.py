"""create immutable weekly occupancy prediction publications

Revision ID: 202608050001
Revises: 202608040001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608050001"
down_revision: str | None = "202608040001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "weekly_occupancy_prediction_publications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("prediction_type", sa.String(32), nullable=False),
        sa.Column("cycle", sa.String(16), nullable=False),
        sa.Column("granularity", sa.String(16), nullable=False),
        sa.Column("scope_type", sa.String(16), nullable=False),
        sa.Column("scope_key", sa.String(160), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=True),
        sa.Column("connector_id", sa.Uuid(), nullable=True),
        sa.Column("timezone", sa.String(128), nullable=False),
        sa.Column("contract_version", sa.String(16), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("external_run_id", sa.String(255), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("publisher_subject_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_export_id", sa.Uuid(), nullable=True),
        sa.Column("training_data_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("training_data_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("canonical_content", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "prediction_type = 'WEEKLY_OCCUPANCY'", name="ck_prediction_publications_type"
        ),
        sa.CheckConstraint("cycle = 'WEEKLY'", name="ck_prediction_publications_cycle"),
        sa.CheckConstraint("granularity = 'HOUR'", name="ck_prediction_publications_granularity"),
        sa.CheckConstraint(
            "contract_version = '1.0'", name="ck_prediction_publications_contract_version"
        ),
        sa.CheckConstraint(
            "(scope_type = 'FACILITY' AND station_id IS NULL AND connector_id IS NULL) OR "
            "(scope_type = 'STATION' AND station_id IS NOT NULL AND connector_id IS NULL) OR "
            "(scope_type = 'CONNECTOR' AND station_id IS NOT NULL AND connector_id IS NOT NULL)",
            name="ck_prediction_publications_scope_shape",
        ),
        sa.CheckConstraint(
            "(training_data_from IS NULL AND training_data_to IS NULL) OR "
            "(training_data_from IS NOT NULL AND training_data_to IS NOT NULL "
            "AND training_data_from < training_data_to)",
            name="ck_prediction_publications_training_window",
        ),
        sa.CheckConstraint(
            "length(content_sha256) = 64 AND content_sha256 = lower(content_sha256)",
            name="ck_prediction_publications_sha256",
        ),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["station_id"], ["charging_stations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["publisher_subject_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["dataset_export_id"], ["dataset_exports.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "scope_key", name="uq_prediction_publications_id_scope"),
        sa.UniqueConstraint(
            "publisher_subject_id",
            "external_run_id",
            "scope_key",
            name="uq_prediction_publications_idempotency",
        ),
    )
    op.create_index(
        "ix_prediction_publications_scope_accepted",
        "weekly_occupancy_prediction_publications",
        ["scope_key", "accepted_at"],
    )
    op.create_index(
        "ix_prediction_publications_scope_generated",
        "weekly_occupancy_prediction_publications",
        ["scope_key", "generated_at"],
    )
    op.create_index(
        "ix_prediction_publications_model",
        "weekly_occupancy_prediction_publications",
        ["model_name", "model_version"],
    )
    op.create_index(
        "ix_prediction_publications_generated_at",
        "weekly_occupancy_prediction_publications",
        ["generated_at"],
    )
    op.create_index(
        "ix_prediction_publications_dataset_export",
        "weekly_occupancy_prediction_publications",
        ["dataset_export_id"],
    )
    op.create_index(
        "ix_prediction_publications_publisher_run",
        "weekly_occupancy_prediction_publications",
        ["publisher_subject_id", "external_run_id"],
    )

    op.create_table(
        "weekly_occupancy_prediction_buckets",
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("day_of_week", sa.String(16), nullable=False),
        sa.Column("hour_of_day", sa.Integer(), nullable=False),
        sa.Column("expected_occupancy_rate", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "day_of_week IN "
            "('MONDAY','TUESDAY','WEDNESDAY','THURSDAY','FRIDAY','SATURDAY','SUNDAY')",
            name="ck_prediction_buckets_weekday",
        ),
        sa.CheckConstraint(
            "hour_of_day >= 0 AND hour_of_day <= 23", name="ck_prediction_buckets_hour"
        ),
        sa.CheckConstraint(
            "expected_occupancy_rate >= 0 AND expected_occupancy_rate <= 1",
            name="ck_prediction_buckets_rate",
        ),
        sa.ForeignKeyConstraint(
            ["publication_id"],
            ["weekly_occupancy_prediction_publications.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("publication_id", "day_of_week", "hour_of_day"),
    )
    op.create_index(
        "ix_prediction_buckets_publication_lookup",
        "weekly_occupancy_prediction_buckets",
        ["publication_id", "day_of_week", "hour_of_day"],
    )

    op.create_table(
        "weekly_occupancy_prediction_current",
        sa.Column("scope_key", sa.String(160), nullable=False),
        sa.Column("scope_type", sa.String(16), nullable=False),
        sa.Column("facility_id", sa.Uuid(), nullable=False),
        sa.Column("station_id", sa.Uuid(), nullable=True),
        sa.Column("connector_id", sa.Uuid(), nullable=True),
        sa.Column("publication_id", sa.Uuid(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(scope_type = 'FACILITY' AND station_id IS NULL AND connector_id IS NULL) OR "
            "(scope_type = 'STATION' AND station_id IS NOT NULL AND connector_id IS NULL) OR "
            "(scope_type = 'CONNECTOR' AND station_id IS NOT NULL AND connector_id IS NOT NULL)",
            name="ck_prediction_current_scope_shape",
        ),
        sa.ForeignKeyConstraint(["facility_id"], ["facilities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["station_id"], ["charging_stations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["connector_id"], ["connectors.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["publication_id", "scope_key"],
            [
                "weekly_occupancy_prediction_publications.id",
                "weekly_occupancy_prediction_publications.scope_key",
            ],
            ondelete="RESTRICT",
            name="fk_prediction_current_publication_scope",
        ),
        sa.PrimaryKeyConstraint("scope_key"),
        sa.UniqueConstraint("publication_id", name="uq_prediction_current_publication"),
    )
    op.create_index(
        "ix_prediction_current_hierarchy",
        "weekly_occupancy_prediction_current",
        ["scope_type", "facility_id", "station_id", "connector_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_prediction_current_hierarchy", table_name="weekly_occupancy_prediction_current"
    )
    op.drop_table("weekly_occupancy_prediction_current")
    op.drop_index(
        "ix_prediction_buckets_publication_lookup",
        table_name="weekly_occupancy_prediction_buckets",
    )
    op.drop_table("weekly_occupancy_prediction_buckets")
    op.drop_index(
        "ix_prediction_publications_publisher_run",
        table_name="weekly_occupancy_prediction_publications",
    )
    op.drop_index(
        "ix_prediction_publications_dataset_export",
        table_name="weekly_occupancy_prediction_publications",
    )
    op.drop_index(
        "ix_prediction_publications_generated_at",
        table_name="weekly_occupancy_prediction_publications",
    )
    op.drop_index(
        "ix_prediction_publications_model",
        table_name="weekly_occupancy_prediction_publications",
    )
    op.drop_index(
        "ix_prediction_publications_scope_generated",
        table_name="weekly_occupancy_prediction_publications",
    )
    op.drop_index(
        "ix_prediction_publications_scope_accepted",
        table_name="weekly_occupancy_prediction_publications",
    )
    op.drop_table("weekly_occupancy_prediction_publications")
