from datetime import datetime, time, timezone

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.db import repo
from app.db.base import get_sessionmaker
from app.keyboards.inline import task_actions_kb
from app.services.occurrences import build_occurrences
from app.utils.dates import parse_date_arg
from app.utils.formatting import (
    format_day_list,
    format_day_sections,
    format_grouped_by_day,
    recurrence_label,
)
from app.utils.tz import to_local, to_utc
from config import Settings

router = Router()

HELP_TEXT = (
    "Я ежедневник 🗓 Просто напиши свободным текстом, что запланировано:\n"
    "• «завтра в 15 встреча с врачом»\n"
    "• «позвонить маме в 9 вечера»\n"
    "• «каждый понедельник в 10 планёрка»\n\n"
    "Команды:\n"
    "/today — задачи на сегодня\n"
    "/list — задачи на дату/период (напр. /list завтра, /list 20.06, /list неделя)\n"
    "/manage — изменить или удалить задачи\n"
    "/timezone — часовой пояс\n"
    "/settings — напоминания и дайджест\n"
    "/cancel — отменить текущее действие"
)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.")


@router.message(Command("manage"))
async def manage_cmd(message: Message, settings: Settings) -> None:
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, message.from_user.id, message.from_user.username,
            settings.default_tz,
        )
        tz_name = user.timezone
        # подчищаем разовые задачи прошлых дней, чтобы не висели в управлении
        today = to_local(_utc_now_naive(), tz_name).date()
        day_start_utc = to_utc(datetime.combine(today, time.min), tz_name)
        await repo.delete_past_one_off(session, user.id, day_start_utc)
        tasks = await repo.list_user_tasks(session, user.id)

    if not tasks:
        await message.answer(
            "У тебя пока нет задач. Напиши, например: «завтра в 15 встреча»."
        )
        return

    await message.answer("🗂 Твои задачи — измени или удали:")
    for task in tasks:
        local = to_local(task.due_at_utc, tz_name)
        label = recurrence_label(task.recurrence)
        suffix = f"  · {label}" if label else ""
        text = f"📝 {task.title}\n🕒 {local:%d.%m.%Y %H:%M}{suffix}"
        await message.answer(text, reply_markup=task_actions_kb(task.id))


@router.message(Command("today"))
async def today_cmd(message: Message, settings: Settings) -> None:
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, message.from_user.id, message.from_user.username,
            settings.default_tz,
        )
        tz_name = user.timezone
        now_utc = _utc_now_naive()
        today = to_local(now_utc, tz_name).date()
        tasks = await repo.list_user_tasks(session, user.id)
    occurrences = build_occurrences(tasks, today, today, tz_name)
    await message.answer(
        format_day_sections(occurrences, tz_name, "📅 Сегодня", now_utc)
    )


@router.message(Command("list"))
async def list_cmd(
    message: Message, command: CommandObject, settings: Settings
) -> None:
    arg = command.args or ""
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, message.from_user.id, message.from_user.username,
            settings.default_tz,
        )
        tz_name = user.timezone
        now_utc = _utc_now_naive()
        today = to_local(now_utc, tz_name).date()
        try:
            start_d, end_d, label = parse_date_arg(arg, today)
        except ValueError:
            await message.answer(
                "Не понял дату 🤔 Примеры:\n"
                "/list завтра\n/list 20.06\n/list неделя"
            )
            return
        tasks = await repo.list_user_tasks(session, user.id)

    occurrences = build_occurrences(tasks, start_d, end_d, tz_name)
    header = f"📅 {label}"
    if start_d == end_d == today:
        # сегодняшний день — делим на предстоящее/прошедшее
        await message.answer(
            format_day_sections(occurrences, tz_name, header, now_utc)
        )
    elif start_d == end_d:
        # другой одиночный день — плоский список
        await message.answer(format_day_list(occurrences, tz_name, header))
    else:
        await message.answer(format_grouped_by_day(occurrences, tz_name, header))
