import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db import repo
from app.db.base import get_sessionmaker
from app.keyboards.inline import settings_kb, timezone_kb
from app.states import SetSettings
from config import Settings

router = Router()

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _settings_text(user) -> str:
    digest = (
        f"включён, в {user.digest_time}" if user.digest_enabled else "выключен"
    )
    return (
        "⚙️ Настройки\n\n"
        f"🌍 Часовой пояс: {user.timezone}\n"
        f"🔔 Дайджест: {digest}\n"
        f"⏰ Напоминать за: {user.default_lead_minutes} мин до события"
    )


async def _get_user(tg_user, settings: Settings):
    maker = get_sessionmaker()
    async with maker() as session:
        return await repo.get_or_create_user(
            session, tg_user.id, tg_user.username, settings.default_tz
        )


async def _update_user(tg_user, settings: Settings, **fields):
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, tg_user.id, tg_user.username, settings.default_tz
        )
        return await repo.update_user(session, user.id, **fields)


@router.message(Command("settings"))
async def settings_cmd(message: Message, settings: Settings) -> None:
    user = await _get_user(message.from_user, settings)
    await message.answer(
        _settings_text(user), reply_markup=settings_kb(user.digest_enabled)
    )


@router.callback_query(F.data == "set:digest_toggle")
async def toggle_digest(cb: CallbackQuery, settings: Settings) -> None:
    user = await _get_user(cb.from_user, settings)
    user = await _update_user(
        cb.from_user, settings, digest_enabled=not user.digest_enabled
    )
    await cb.message.edit_text(
        _settings_text(user), reply_markup=settings_kb(user.digest_enabled)
    )
    await cb.answer("Обновлено")


@router.callback_query(F.data == "set:digest_time")
async def ask_digest_time(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetSettings.waiting_digest_time)
    await cb.message.answer(
        "Пришли время дайджеста в формате ЧЧ:ММ (напр. 09:00). /cancel — отмена."
    )
    await cb.answer()


@router.message(SetSettings.waiting_digest_time, F.text & ~F.text.startswith("/"))
async def set_digest_time(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    m = _TIME_RE.match(message.text.strip())
    if not m:
        await message.answer("Формат ЧЧ:ММ, напр. 09:00. Попробуй ещё раз или /cancel.")
        return
    hhmm = f"{int(m.group(1)):02d}:{m.group(2)}"
    user = await _update_user(
        message.from_user, settings, digest_time=hhmm, digest_enabled=True
    )
    await state.clear()
    await message.answer(
        f"✅ Дайджест будет приходить в {hhmm}.",
        reply_markup=settings_kb(user.digest_enabled),
    )


@router.callback_query(F.data == "set:lead")
async def ask_lead(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetSettings.waiting_lead)
    await cb.message.answer(
        "За сколько минут до события напоминать? Пришли число (напр. 15). "
        "/cancel — отмена."
    )
    await cb.answer()


@router.message(SetSettings.waiting_lead, F.text & ~F.text.startswith("/"))
async def set_lead(message: Message, state: FSMContext, settings: Settings) -> None:
    txt = message.text.strip()
    if not txt.isdigit() or not (0 <= int(txt) <= 1440):
        await message.answer(
            "Нужно число от 0 до 1440 (минут). Попробуй ещё раз или /cancel."
        )
        return
    user = await _update_user(
        message.from_user, settings, default_lead_minutes=int(txt)
    )
    await state.clear()
    await message.answer(
        f"✅ Буду напоминать за {int(txt)} мин до события.",
        reply_markup=settings_kb(user.digest_enabled),
    )


@router.callback_query(F.data == "set:tz")
async def settings_tz(cb: CallbackQuery) -> None:
    await cb.message.answer("🌍 Выбери часовой пояс:", reply_markup=timezone_kb())
    await cb.answer()
