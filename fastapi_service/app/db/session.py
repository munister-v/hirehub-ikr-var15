"""Асинхронний engine і сесія; залежність get_session для Depends."""
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_factory: async_sessionmaker[AsyncSession] | None = None


def make_engine(url: str) -> AsyncEngine:
    kwargs = {}
    if url.startswith('sqlite') and ':memory:' in url:
        kwargs = {'poolclass': StaticPool, 'connect_args': {'check_same_thread': False}}
    return create_async_engine(url, **kwargs)


def init_engine(url: str | None = None) -> AsyncEngine:
    global _engine, _factory
    _engine = make_engine(url or get_settings().database_url)
    _factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_engine() -> AsyncEngine:
    return _engine if _engine is not None else init_engine()


def session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    return _factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """Одна сесія на запит; commit/rollback виконує сервісний шар."""
    async with session_factory()() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _factory
    if _engine is not None:
        await _engine.dispose()
    _engine = _factory = None
