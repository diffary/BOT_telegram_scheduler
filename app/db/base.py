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


def init_engine(db_path: str) -> AsyncEngine:
    """Создать async-engine и фабрику сессий для SQLite по пути db_path."""
    global _engine, _sessionmaker
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
