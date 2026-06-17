from datetime import date, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db import repo
from app.db.base import Base


@pytest.fixture
async def session():
    """Свежая in-memory БД на каждый тест."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_get_or_create_user_creates_then_reuses(session):
    u1 = await repo.get_or_create_user(
        session, telegram_id=42, username="bob", default_tz="Europe/Moscow"
    )
    u2 = await repo.get_or_create_user(
        session, telegram_id=42, username="bob", default_tz="Europe/Moscow"
    )
    assert u1.id is not None
    assert u1.id == u2.id  # второй вызов не плодит дубль
    # дефолты из модели применились
    assert u1.timezone == "Europe/Moscow"
    assert u1.default_lead_minutes == 15
    assert u1.digest_enabled is True


async def test_get_user_by_telegram_id(session):
    assert await repo.get_user_by_telegram_id(session, 99) is None
    await repo.get_or_create_user(session, 99, "x", "Europe/Moscow")
    found = await repo.get_user_by_telegram_id(session, 99)
    assert found is not None
    assert found.telegram_id == 99


async def test_create_task(session):
    user = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    task = await repo.create_task(
        session,
        user_id=user.id,
        title="встреча с врачом",
        raw_text="завтра в 15 врач",
        due_at_utc=datetime(2026, 6, 17, 12, 0),
        recurrence="none",
    )
    assert task.id is not None
    assert task.user_id == user.id
    assert task.title == "встреча с врачом"
    assert task.recurrence == "none"
    assert task.last_reminded_on is None


async def test_get_user_tasks_for_date(session):
    user = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    # две задачи на 17-е (в разное время) и одна на 18-е
    await repo.create_task(
        session, user.id, "поздняя", "r",
        datetime(2026, 6, 17, 18, 0),
    )
    await repo.create_task(
        session, user.id, "ранняя", "r",
        datetime(2026, 6, 17, 9, 0),
    )
    await repo.create_task(
        session, user.id, "другой день", "r",
        datetime(2026, 6, 18, 10, 0),
    )

    tasks = await repo.get_user_tasks_for_date(session, user.id, date(2026, 6, 17))

    assert [t.title for t in tasks] == ["ранняя", "поздняя"]  # отсортировано по времени


async def test_get_user_tasks_for_date_isolated_by_user(session):
    u1 = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    u2 = await repo.get_or_create_user(session, 2, "b", "Europe/Moscow")
    await repo.create_task(session, u1.id, "моя", "r", datetime(2026, 6, 17, 9, 0))
    await repo.create_task(session, u2.id, "чужая", "r", datetime(2026, 6, 17, 9, 0))

    tasks = await repo.get_user_tasks_for_date(session, u1.id, date(2026, 6, 17))
    assert [t.title for t in tasks] == ["моя"]


async def test_update_task(session):
    user = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    task = await repo.create_task(
        session, user.id, "старое", "r", datetime(2026, 6, 17, 9, 0)
    )
    updated = await repo.update_task(
        session, task.id, user.id, title="новое", recurrence="daily"
    )
    assert updated is not None
    assert updated.title == "новое"
    assert updated.recurrence == "daily"


async def test_update_task_foreign_user_returns_none(session):
    owner = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    other = await repo.get_or_create_user(session, 2, "b", "Europe/Moscow")
    task = await repo.create_task(
        session, owner.id, "t", "r", datetime(2026, 6, 17, 9, 0)
    )
    assert await repo.update_task(session, task.id, other.id, title="хак") is None


async def test_delete_task(session):
    user = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    task = await repo.create_task(
        session, user.id, "t", "r", datetime(2026, 6, 17, 9, 0)
    )
    await repo.delete_task(session, task.id, user.id)
    assert await repo.get_user_tasks_for_date(
        session, user.id, date(2026, 6, 17)
    ) == []


async def test_delete_past_one_off(session):
    u = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    await repo.create_task(session, u.id, "вчерашняя", "r",
                           datetime(2026, 6, 16, 9, 0))  # разовая, прошлый день
    await repo.create_task(session, u.id, "сегодня", "r",
                           datetime(2026, 6, 18, 9, 0))  # разовая, сегодня
    await repo.create_task(session, u.id, "повтор", "r",
                           datetime(2026, 6, 10, 9, 0), recurrence="daily")

    before = datetime(2026, 6, 18, 0, 0)  # начало сегодняшнего дня (UTC)
    n = await repo.delete_past_one_off(session, u.id, before)

    assert n == 1  # удалилась только вчерашняя разовая
    titles = [t.title for t in await repo.list_user_tasks(session, u.id)]
    assert "вчерашняя" not in titles
    assert "сегодня" in titles and "повтор" in titles


async def test_update_last_reminded(session):
    user = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    task = await repo.create_task(
        session, user.id, "t", "r", datetime(2026, 6, 17, 9, 0)
    )
    await repo.update_last_reminded(session, task.id, date(2026, 6, 17))
    refreshed = (
        await repo.get_user_tasks_for_date(session, user.id, date(2026, 6, 17))
    )[0]
    assert refreshed.last_reminded_on == date(2026, 6, 17)
