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


def test_technical_client_profile_migration_upgrades_and_downgrades() -> None:
    assert DATABASE_URL is not None
    backend = Path(__file__).resolve().parents[3]
    configuration = Config(str(backend / "alembic.ini"))
    configuration.set_main_option("script_location", str(backend / "alembic"))
    configuration.set_main_option("sqlalchemy.url", DATABASE_URL)
    engine = create_engine(DATABASE_URL)
    try:
        command.upgrade(configuration, "head")
        assert "technical_profile" in {
            column["name"] for column in inspect(engine).get_columns("users")
        }
        command.downgrade(configuration, "202608010001")
        assert "technical_profile" not in {
            column["name"] for column in inspect(engine).get_columns("users")
        }
    finally:
        command.upgrade(configuration, "head")
        engine.dispose()
