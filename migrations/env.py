import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.models import Base

config = context.config
target_metadata = Base.metadata


def get_database_url() -> str:
    """Resolve a non-production migration URL without reading a .env file."""
    url = os.environ.get("ALEMBIC_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        url = config.get_main_option("sqlalchemy.url")
    # The application uses asyncpg while Alembic requires a synchronous driver.
    return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)


def run_migrations_offline():
    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    config.set_main_option("sqlalchemy.url", get_database_url())
    connectable = engine_from_config(
        config.get_section(config.config_ini_section), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
