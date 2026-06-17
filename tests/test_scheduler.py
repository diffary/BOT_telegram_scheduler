from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db import repo
from app.db.base import Base
from app.services import scheduler


@pytest.fixture
async def maker():
    # StaticPool + один in-memory engine -> данные видны во всех сессиях.
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:", poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


class MockBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


async def test_collect_due_reminders_finds_due_task(maker):
    async with maker() as s:
        u = await repo.get_or_create_user(s, 1, "a", "Europe/Moscow")
        await repo.create_task(
            s, u.id, "врач", "r", datetime(2026, 6, 17, 12, 0), lead_minutes=15
        )
        due = await scheduler.collect_due_reminders(
            s, now_utc=datetime(2026, 6, 17, 11, 50)
        )
    assert len(due) == 1
    user, task, occ = due[0]
    assert task.title == "врач"
    assert occ == datetime(2026, 6, 17, 12, 0)


async def test_collect_due_reminders_empty_when_too_early(maker):
    async with maker() as s:
        u = await repo.get_or_create_user(s, 1, "a", "Europe/Moscow")
        await repo.create_task(
            s, u.id, "врач", "r", datetime(2026, 6, 17, 12, 0), lead_minutes=15
        )
        due = await scheduler.collect_due_reminders(
            s, now_utc=datetime(2026, 6, 17, 10, 0)
        )
    assert due == []


async def test_collect_digests_respects_time_and_toggle(maker):
    async with maker() as s:
        # юзер с дайджестом в 09:00 MSK -> 06:00 UTC
        u = await repo.get_or_create_user(s, 1, "a", "Europe/Moscow")
        # дайджест в неподходящее время -> пусто
        none_yet = await scheduler.collect_digests(
            s, now_utc=datetime(2026, 6, 17, 5, 0)
        )
        assert none_yet == []
        # ровно 06:00 UTC == 09:00 MSK -> попадает
        hit = await scheduler.collect_digests(
            s, now_utc=datetime(2026, 6, 17, 6, 0)
        )
        assert len(hit) == 1 and hit[0][0].id == u.id


async def test_collect_digests_skips_disabled(maker):
    async with maker() as s:
        u = await repo.get_or_create_user(s, 1, "a", "Europe/Moscow")
        await repo.update_user(s, u.id, digest_enabled=False)
        hit = await scheduler.collect_digests(
            s, now_utc=datetime(2026, 6, 17, 6, 0)
        )
    assert hit == []


async def test_tick_sends_reminder_and_marks(maker, monkeypatch):
    # make_tick использует глобальный get_sessionmaker -> подменяем на наш maker
    monkeypatch.setattr(scheduler, "get_sessionmaker", lambda: maker)
    monkeypatch.setattr(
        scheduler, "_now_utc_minute", lambda: datetime(2026, 6, 17, 11, 50)
    )

    async with maker() as s:
        u = await repo.get_or_create_user(s, 1, "a", "Europe/Moscow")
        # дайджест выключим, чтобы не мешал проверке напоминания
        await repo.update_user(s, u.id, digest_enabled=False)
        task = await repo.create_task(
            s, u.id, "врач", "r", datetime(2026, 6, 17, 12, 0), lead_minutes=15
        )

    bot = MockBot()
    tick = scheduler.make_tick(bot)
    await tick()

    assert len(bot.sent) == 1
    chat_id, text = bot.sent[0]
    assert chat_id == 1
    assert "врач" in text

    # last_reminded_on проставлен -> повторно не шлёт
    await tick()
    assert len(bot.sent) == 1
