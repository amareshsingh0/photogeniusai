"""Alembic env. Run migrations with `alembic upgrade head`."""

import asyncio
from logging.config import fileConfig

from alembic import context  # type: ignore[reportAttributeAccessIssue]
from sqlalchemy import pool  # type: ignore[reportMissingImports]
from sqlalchemy.engine import Connection  # type: ignore[reportMissingImports]
from sqlalchemy.ext.asyncio import async_engine_from_config  # type: ignore[reportMissingImports]

from app.core.config import get_settings
from app.core.database import get_async_database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
# Convert DATABASE_URL to string and use async format
database_url = get_async_database_url()
# Set URL directly in config dict to avoid ConfigParser interpolation issues
config.attributes['sqlalchemy.url'] = database_url
# Import Base to get metadata
from app.core.database import Base
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # Get URL from attributes or main option
    url = config.attributes.get("sqlalchemy.url") or config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async() -> None:
    # Get URL from attributes
    url = config.attributes.get("sqlalchemy.url")
    if url:
        # Create engine directly with URL
        from sqlalchemy.ext.asyncio import create_async_engine  # type: ignore[reportMissingImports]
        connectable = create_async_engine(url, poolclass=pool.NullPool)
    else:
        # Fallback to config-based approach
        connectable = async_engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
