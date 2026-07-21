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


def test_dataset_export_migration_upgrades_and_downgrades() -> None:
    assert DATABASE_URL is not None
    backend = Path(__file__).resolve().parents[3]
    configuration = Config(str(backend / "alembic.ini"))
    configuration.set_main_option("script_location", str(backend / "alembic"))
    configuration.set_main_option("sqlalchemy.url", DATABASE_URL)
    engine = create_engine(DATABASE_URL)
    try:
        command.downgrade(configuration, "202607180001")
        assert "dataset_exports" not in inspect(engine).get_table_names()
        command.upgrade(configuration, "head")
        inspector = inspect(engine)
        assert "dataset_exports" in inspector.get_table_names()
        indexes = {item["name"] for item in inspector.get_indexes("dataset_exports")}
        assert {
            "ix_dataset_exports_status_created",
            "ix_dataset_exports_owner_created",
            "ix_dataset_exports_artifact_expires",
        }.issubset(indexes)
    finally:
        command.upgrade(configuration, "head")
        engine.dispose()
