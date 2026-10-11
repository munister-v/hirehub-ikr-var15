"""Alembic з асинхронним engine: міграції виконуються тим самим драйвером, що й сервіс (asyncpg / aiosqlite)."""
import asyncio
import os

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import get_settings
from app.db.base import Base
from app import models  # noqa: F401  — реєструє таблиці в Base.metadata

config = context.config
target_metadata = Base.metadata


def _url() -> str:
    return os.environ.get('MATCHING_DATABASE_URL') or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _do_run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section['sqlalchemy.url'] = _url()
    engine = async_engine_from_config(section, prefix='sqlalchemy.', poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(_do_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
