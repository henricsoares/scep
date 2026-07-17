from logging.config import fileConfig

from alembic import context
from app.core.config import get_settings
from app.infrastructure.database import Base
from app.modules.charging.infrastructure import FacilityModel
from app.modules.events import infrastructure as events_infrastructure
from app.modules.identity.infrastructure import user_model
from app.modules.telemetry import infrastructure as telemetry_infrastructure
from sqlalchemy import engine_from_config, pool

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

_ = (FacilityModel, user_model, telemetry_infrastructure, events_infrastructure)
target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
