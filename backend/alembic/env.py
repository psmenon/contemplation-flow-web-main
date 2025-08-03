import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine

from alembic import context

from src.db import meta
from src.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = meta


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_async_engine(str(settings.db_url))
    if isinstance(connectable, AsyncEngine):
        asyncio.run(run_async_migrations(connectable))
    else:
        do_run_migrations(connectable)


async def run_async_migrations(connectable):
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


run_migrations_online()
