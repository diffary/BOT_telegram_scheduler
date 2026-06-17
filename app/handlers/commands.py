from datetime import datetime, time, timedelta, timezone

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.db import repo
from app.db.base import get_sessionmaker
from app.utils.dates import parse_date_arg
from app.utils.formatting import (
    format_day_list,
    format_day_sections,
    format_grouped_by_day,
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
    "/timezone — часовой пояс\n"
    "/settings — напоминания и дайджест\n"
    "/cancel — отменить текущее действие"
)


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _day_bounds_utc(start_d, end_d, tz_name):
    """Локальный диапазон дней [start_d .. end_d] -> границы в UTC [start, end)."""
    start_utc = to_utc(datetime.combine(start_d, time.min), tz_name)
    end_utc = to_utc(datetime.combine(end_d + timedelta(days=1), time.min), tz_name)
    return start_utc, end_utc


@router.message(Command("help"))
async def help_cmd(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.")


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
        start_utc, end_utc = _day_bounds_utc(today, today, tz_name)
        tasks = await repo.get_user_tasks_in_range(
            session, user.id, start_utc, end_utc
        )
    await message.answer(
        format_day_sections(tasks, tz_name, "📅 Сегодня", now_utc)
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
        start_utc, end_utc = _day_bounds_utc(start_d, end_d, tz_name)
        tasks = await repo.get_user_tasks_in_range(
            session, user.id, start_utc, end_utc
        )

    header = f"📅 {label}"
    if start_d == end_d == today:
        # сегодняшний день — делим на предстоящее/прошедшее
        await message.answer(
            format_day_sections(tasks, tz_name, header, now_utc)
        )
    elif start_d == end_d:
        # другой одиночный день — плоский список
        await message.answer(format_day_list(tasks, tz_name, header))
    else:
        await message.answer(format_grouped_by_day(tasks, tz_name, header))
