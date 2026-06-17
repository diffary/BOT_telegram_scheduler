from datetime import date, datetime, time, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Task, User

# Дневной лимит AI-распознаваний для бесплатного тарифа.
FREE_DAILY_AI_LIMIT = 20


async def get_user_by_telegram_id(
    session: AsyncSession, telegram_id: int
) -> User | None:
    """Вернуть пользователя по telegram_id или None."""
    res = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return res.scalar_one_or_none()


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None,
    default_tz: str,
) -> User:
    """Вернуть существующего пользователя или создать нового."""
    user = await get_user_by_telegram_id(session, telegram_id)
    if user is None:
        user = User(
            telegram_id=telegram_id, username=username, timezone=default_tz
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def update_user(
    session: AsyncSession, user_id: int, **fields
) -> User | None:
    """Обновить поля пользователя (часовой пояс, настройки дайджеста и т.д.)."""
    user = await session.get(User, user_id)
    if user is None:
        return None
    for key, value in fields.items():
        setattr(user, key, value)
    await session.commit()
    await session.refresh(user)
    return user


async def create_task(
    session: AsyncSession,
    user_id: int,
    title: str,
    raw_text: str,
    due_at_utc: datetime,
    recurrence: str = "none",
    recurrence_weekday: int | None = None,
    lead_minutes: int | None = None,
) -> Task:
    """Создать задачу и вернуть её."""
    task = Task(
        user_id=user_id,
        title=title,
        raw_text=raw_text,
        due_at_utc=due_at_utc,
        recurrence=recurrence,
        recurrence_weekday=recurrence_weekday,
        lead_minutes=lead_minutes,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def get_user_tasks_for_date(
    session: AsyncSession, user_id: int, day: date
) -> list[Task]:
    """Вернуть задачи пользователя, у которых due_at_utc приходится на день `day`
    (по UTC-дате), отсортированные по времени.

    На этом этапе учитываются только разовые задачи (по фактической дате
    due_at_utc). Раскрытие повторяющихся задач по дням — отдельный этап.
    """
    start = datetime.combine(day, time.min)
    end = start + timedelta(days=1)
    res = await session.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.due_at_utc >= start,
            Task.due_at_utc < end,
        )
        .order_by(Task.due_at_utc)
    )
    return list(res.scalars().all())


async def list_user_tasks(session: AsyncSession, user_id: int) -> list[Task]:
    """Все задачи пользователя (для раскрытия повторов в просмотре)."""
    res = await session.execute(
        select(Task).where(Task.user_id == user_id).order_by(Task.due_at_utc)
    )
    return list(res.scalars().all())


async def get_user_tasks_in_range(
    session: AsyncSession, user_id: int, start_utc: datetime, end_utc: datetime
) -> list[Task]:
    """Задачи пользователя с due_at_utc в полуинтервале [start_utc, end_utc),
    отсортированные по времени. Границы считаются в UTC — вызывающий код
    переводит локальный день пользователя в UTC заранее.
    """
    res = await session.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.due_at_utc >= start_utc,
            Task.due_at_utc < end_utc,
        )
        .order_by(Task.due_at_utc)
    )
    return list(res.scalars().all())


async def get_task(
    session: AsyncSession, task_id: int, user_id: int
) -> Task | None:
    """Вернуть задачу пользователя по id или None."""
    res = await session.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user_id)
    )
    return res.scalar_one_or_none()


async def update_task(
    session: AsyncSession, task_id: int, user_id: int, **fields
) -> Task | None:
    """Обновить поля задачи (только своей). Вернуть задачу или None."""
    task = await get_task(session, task_id, user_id)
    if task is None:
        return None
    for key, value in fields.items():
        setattr(task, key, value)
    await session.commit()
    await session.refresh(task)
    return task


async def delete_task(
    session: AsyncSession, task_id: int, user_id: int
) -> None:
    """Удалить задачу пользователя."""
    await session.execute(
        delete(Task).where(Task.id == task_id, Task.user_id == user_id)
    )
    await session.commit()


async def delete_past_one_off(
    session: AsyncSession, user_id: int, before_utc: datetime
) -> int:
    """Удалить РАЗОВЫЕ задачи пользователя со временем раньше before_utc.

    Повторяющиеся (recurrence != 'none') не трогаются. Возвращает число удалённых.
    """
    res = await session.execute(
        delete(Task).where(
            Task.user_id == user_id,
            Task.recurrence == "none",
            Task.due_at_utc < before_utc,
        )
    )
    await session.commit()
    return res.rowcount or 0


async def update_last_reminded(
    session: AsyncSession, task_id: int, day: date
) -> None:
    """Проставить last_reminded_on задаче (защита от повторных напоминаний)."""
    task = await session.get(Task, task_id)
    if task is not None:
        task.last_reminded_on = day
        await session.commit()


async def all_users(session: AsyncSession) -> list[User]:
    """Все пользователи (для планировщика)."""
    res = await session.execute(select(User))
    return list(res.scalars().all())


async def all_tasks(session: AsyncSession) -> list[Task]:
    """Все задачи всех пользователей (для планировщика)."""
    res = await session.execute(select(Task))
    return list(res.scalars().all())


def is_premium(user: User, now_utc: datetime) -> bool:
    """Активен ли у пользователя премиум на момент now_utc."""
    if user.plan != "premium":
        return False
    return user.premium_until is None or user.premium_until >= now_utc


async def record_ai_request(
    session: AsyncSession, user_id: int, today: date
) -> int:
    """Учесть один AI-запрос с авто-сбросом счётчика на новый день.

    Возвращает число использованных запросов за сегодня (после инкремента).
    """
    user = await session.get(User, user_id)
    if user is None:
        return 0
    if user.ai_requests_date != today:
        user.ai_requests_date = today
        user.ai_requests_used = 0
    user.ai_requests_used += 1
    await session.commit()
    return user.ai_requests_used
