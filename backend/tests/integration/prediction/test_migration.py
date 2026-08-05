from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="POSTGRES_TEST_DATABASE_URL is required for migration integration tests",
)


def test_prediction_migration_upgrades_and_downgrades() -> None:
    assert DATABASE_URL is not None
    backend = Path(__file__).resolve().parents[3]
    configuration = Config(str(backend / "alembic.ini"))
    configuration.set_main_option("script_location", str(backend / "alembic"))
    configuration.set_main_option("sqlalchemy.url", DATABASE_URL)
    engine = create_engine(DATABASE_URL)
    try:
        command.downgrade(configuration, "202608040001")
        inspector = inspect(engine)
        assert "weekly_occupancy_prediction_publications" not in inspector.get_table_names()
        command.upgrade(configuration, "head")
        inspector = inspect(engine)
        assert {
            "weekly_occupancy_prediction_publications",
            "weekly_occupancy_prediction_buckets",
            "weekly_occupancy_prediction_current",
        }.issubset(inspector.get_table_names())
        publication_indexes = {
            item["name"]
            for item in inspector.get_indexes("weekly_occupancy_prediction_publications")
        }
        assert {
            "ix_prediction_publications_scope_accepted",
            "ix_prediction_publications_scope_generated",
            "ix_prediction_publications_model",
            "ix_prediction_publications_publisher_run",
        }.issubset(publication_indexes)
        bucket_checks = {
            item["name"]
            for item in inspector.get_check_constraints("weekly_occupancy_prediction_buckets")
        }
        assert {
            "ck_prediction_buckets_weekday",
            "ck_prediction_buckets_hour",
            "ck_prediction_buckets_rate",
        }.issubset(bucket_checks)
        current_uniques = {
            item["name"]
            for item in inspector.get_unique_constraints("weekly_occupancy_prediction_current")
        }
        assert "uq_prediction_current_publication" in current_uniques
    finally:
        command.upgrade(configuration, "head")
        engine.dispose()
