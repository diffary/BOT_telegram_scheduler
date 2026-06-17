import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.db import repo
from app.db.base import get_sessionmaker
from app.services.occurrences import (
    build_occurrences,
    is_reminder_due,
    occurrence_on_date,
)
from app.utils.formatting import format_day_list
from app.utils.tz import to_local

log = logging.getLogger(__name__)


def _now_utc_minute() -> datetime:
    """Текущее время UTC, обрезанное до минуты (гранулярность тика)."""
    return datetime.now(timezone.utc).replace(tzinfo=None, second=0, microsecond=0)


async def collect_due_reminders(session, now_utc: datetime):
    """-> список (user, task, occurrence_utc) для созревших напоминаний."""
    users = {u.id: u for u in await repo.all_users(session)}
    result = []
    for task in await repo.all_tasks(session):
        user = users.get(task.user_id)
        if user is None:
            continue
        if is_reminder_due(task, now_utc, user.default_lead_minutes):
            occ = occurrence_on_date(task, now_utc.date())
            result.append((user, task, occ))
    return result


async def collect_digests(session, now_utc: datetime):
    """-> список (user, tasks_today) для тех, у кого сейчас время дайджеста.

    Дайджест модульный: только если digest_enabled и локальное время
    совпадает с digest_time пользователя.
    """
    result = []
    for user in await repo.all_users(session):
        if not user.digest_enabled:
            continue
        local_now = to_local(now_utc, user.timezone)
        if local_now.strftime("%H:%M") != user.digest_time:
            continue
        today = local_now.date()
        # как и в /today — раскрываем повторы на сегодня
        tasks = await repo.list_user_tasks(session, user.id)
        occurrences = build_occurrences(tasks, today, today, user.timezone)
        result.append((user, occurrences))
    return result


def make_tick(bot):
    """Создать корутину-тик. bot — для отправки сообщений."""
    # Защита от повторной отправки дайджеста в ту же минуту/при дребезге.
    digest_sent: set[tuple[int, object]] = set()

    async def tick() -> None:
        now_utc = _now_utc_minute()
        maker = get_sessionmaker()
        async with maker() as session:
            try:
                for user, task, occ in await collect_due_reminders(session, now_utc):
                    try:
                        local = to_local(occ, user.timezone)
                        await bot.send_message(
                            user.telegram_id,
                            f"🔔 Напоминание: {task.title} в {local:%H:%M}",
                        )
                        await repo.update_last_reminded(
                            session, task.id, now_utc.date()
                        )
                    except Exception:
                        log.exception(
                            "reminder failed for user %s", user.telegram_id
                        )

                for user, tasks in await collect_digests(session, now_utc):
                    key = (user.id, to_local(now_utc, user.timezone).date())
                    if key in digest_sent:
                        continue
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            format_day_list(
                                tasks, user.timezone, "☀️ План на сегодня"
                            ),
                        )
                        digest_sent.add(key)
                    except Exception:
                        log.exception("digest failed for user %s", user.telegram_id)
            except Exception:
                log.exception("scheduler tick failed")

    return tick


def start_scheduler(bot, interval_seconds: int) -> AsyncIOScheduler:
    """Запустить планировщик с одним тиком раз в interval_seconds."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(make_tick(bot), "interval", seconds=interval_seconds)
    scheduler.start()
    return scheduler
