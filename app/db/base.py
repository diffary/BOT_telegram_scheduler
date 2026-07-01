from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def init_engine(db_path: str, database_url: str | None = None) -> AsyncEngine:
    """Создать async-engine и фабрику сессий.

    Если задан database_url (напр. Postgres/Supabase) — используем его,
    иначе локальный SQLite по db_path.
    """
    global _engine, _sessionmaker
    if database_url:
        url = database_url
        # позволяем вставлять строку Supabase как есть (postgresql://...)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        connect_args = {}
        if "asyncpg" in url:
            # Supabase/pgbouncer-пул не дружит с кэшем prepared statements asyncpg
            connect_args["statement_cache_size"] = 0
        _engine = create_async_engine(
            url, pool_pre_ping=True, connect_args=connect_args
        )
    else:
        _engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def init_db() -> None:
    """Создать таблицы (CREATE TABLE IF NOT EXISTS) по метаданным моделей."""
    if _engine is None:
        raise RuntimeError("Engine не инициализирован: сначала вызови init_engine()")
    # Импорт моделей регистрирует их в Base.metadata.
    from app.db import models  # noqa: F401

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Вернуть фабрику сессий (после init_engine)."""
    if _sessionmaker is None:
        raise RuntimeError("Engine не инициализирован: сначала вызови init_engine()")
    return _sessionmaker
