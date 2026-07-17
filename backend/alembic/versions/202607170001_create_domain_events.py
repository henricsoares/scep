"""create immutable domain event store and deliveries

Revision ID: 202607170001
Revises: 202607150001
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202607170001"
down_revision: str | None = "202607150001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "domain_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(128), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False),
        sa.Column("aggregate_id", sa.Uuid(), nullable=False),
        sa.Column("aggregate_type", sa.String(128), nullable=False),
        sa.Column("producer_module", sa.String(64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
        sa.Column("causation_id", sa.Uuid(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("event_version > 0", name="ck_domain_events_version"),
        sa.CheckConstraint(
            "jsonb_typeof(payload::jsonb) = 'object'", name="ck_domain_events_payload_object"
        ),
        sa.CheckConstraint(
            "jsonb_typeof(metadata::jsonb) = 'object'", name="ck_domain_events_metadata_object"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_domain_events_occurred_id", "domain_events", ["occurred_at", "id"])
    op.create_index("ix_domain_events_type", "domain_events", ["event_type"])
    op.create_index("ix_domain_events_aggregate", "domain_events", ["aggregate_type", "aggregate_id"])
    op.create_index("ix_domain_events_producer", "domain_events", ["producer_module"])
    op.create_table(
        "event_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("consumer", sa.String(128), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_event_delivery_attempts"),
        sa.CheckConstraint("status IN ('PENDING','DISPATCHED','FAILED')", name="ck_event_delivery_status"),
        sa.ForeignKeyConstraint(["event_id"], ["domain_events.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_event_delivery_event_consumer", "event_deliveries", ["event_id", "consumer"], unique=True)
    op.create_index("ix_event_delivery_eligible", "event_deliveries", ["status", "updated_at"])
    op.execute("""
        CREATE FUNCTION reject_domain_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'domain events are immutable'; END; $$ LANGUAGE plpgsql;
        CREATE TRIGGER domain_events_immutable_update BEFORE UPDATE ON domain_events
        FOR EACH ROW EXECUTE FUNCTION reject_domain_event_mutation();
        CREATE TRIGGER domain_events_immutable_delete BEFORE DELETE ON domain_events
        FOR EACH ROW EXECUTE FUNCTION reject_domain_event_mutation();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER domain_events_immutable_delete ON domain_events")
    op.execute("DROP TRIGGER domain_events_immutable_update ON domain_events")
    op.execute("DROP FUNCTION reject_domain_event_mutation()")
    op.drop_index("ix_event_delivery_eligible", table_name="event_deliveries")
    op.drop_index("uq_event_delivery_event_consumer", table_name="event_deliveries")
    op.drop_table("event_deliveries")
    op.drop_index("ix_domain_events_producer", table_name="domain_events")
    op.drop_index("ix_domain_events_aggregate", table_name="domain_events")
    op.drop_index("ix_domain_events_type", table_name="domain_events")
    op.drop_index("ix_domain_events_occurred_id", table_name="domain_events")
    op.drop_table("domain_events")
