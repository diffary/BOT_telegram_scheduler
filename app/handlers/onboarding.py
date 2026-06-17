from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db import repo
from app.db.base import get_sessionmaker
from app.keyboards.inline import timezone_kb
from app.states import SetTimezone
from app.utils.tz import is_valid_tz
from config import Settings

router = Router()

WELCOME = (
    "Привет! Я ежедневник 🗓\n"
    "Напиши свободным текстом, что запланировано — например:\n"
    "• «завтра в 15 встреча с врачом»\n"
    "• «каждый понедельник в 10 планёрка»\n\n"
    "Команды: /today, /list, /manage, /settings, /help"
)


async def _resolve(tg_user, settings: Settings):
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, tg_user.id, tg_user.username, settings.default_tz
        )
        return user.timezone


@router.message(CommandStart())
async def start_cmd(message: Message, settings: Settings) -> None:
    tz = await _resolve(message.from_user, settings)
    await message.answer(WELCOME)
    await message.answer(
        f"🌍 Часовой пояс сейчас: {tz}\n"
        "Выбери свой, чтобы напоминания приходили вовремя:",
        reply_markup=timezone_kb(),
    )


@router.message(Command("timezone"))
async def timezone_cmd(message: Message, settings: Settings) -> None:
    tz = await _resolve(message.from_user, settings)
    await message.answer(
        f"🌍 Сейчас: {tz}\nВыбери часовой пояс:", reply_markup=timezone_kb()
    )


async def _save_tz(tg_user, settings: Settings, tz: str) -> None:
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, tg_user.id, tg_user.username, settings.default_tz
        )
        await repo.update_user(session, user.id, timezone=tz)


@router.callback_query(F.data.startswith("tz:set:"))
async def tz_set(cb: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    tz = cb.data[len("tz:set:"):]
    if not is_valid_tz(tz):
        await cb.answer("Неизвестный пояс.", show_alert=True)
        return
    await _save_tz(cb.from_user, settings, tz)
    await state.clear()
    await cb.message.edit_text(f"✅ Часовой пояс установлен: {tz}")
    await cb.answer("Готово")


@router.callback_query(F.data == "tz:manual")
async def tz_manual(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(SetTimezone.waiting_manual)
    await cb.message.answer(
        "Пришли часовой пояс в формате IANA, напр. Europe/Kyiv или Asia/Almaty. "
        "/cancel — отмена."
    )
    await cb.answer()


@router.message(SetTimezone.waiting_manual, F.text & ~F.text.startswith("/"))
async def tz_manual_input(
    message: Message, state: FSMContext, settings: Settings
) -> None:
    tz = message.text.strip()
    if not is_valid_tz(tz):
        await message.answer(
            "Не узнал пояс. Примеры: Europe/Kyiv, Europe/Moscow, Asia/Almaty. "
            "Попробуй ещё раз или /cancel."
        )
        return
    await _save_tz(message.from_user, settings, tz)
    await state.clear()
    await message.answer(f"✅ Часовой пояс установлен: {tz}")
