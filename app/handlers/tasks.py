import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db import repo
from app.db.base import get_sessionmaker
from app.keyboards.inline import confirm_kb
from app.services.gemini import GeminiService, GeminiUnavailable
from app.services.parser import NeedsClarification, ParseError, parse
from app.utils.tz import to_local
from config import Settings

log = logging.getLogger(__name__)
router = Router()

_REC_LABEL = {
    "none": "",
    "daily": " · ежедневно",
    "weekly": " · еженедельно",
    "monthly": " · ежемесячно",
}


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _format_card(title: str, due_at_utc: datetime, recurrence: str, tz_name: str) -> str:
    local = to_local(due_at_utc, tz_name)
    label = _REC_LABEL.get(recurrence, "")
    return f"📝 {title}\n🕒 {local:%d.%m.%Y %H:%M}{label}"


@router.message(F.text & ~F.text.startswith("/"))
async def on_free_text(
    message: Message,
    state: FSMContext,
    gemini: GeminiService,
    settings: Settings,
) -> None:
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session,
            message.from_user.id,
            message.from_user.username,
            settings.default_tz,
        )
        tz_name = user.timezone

    now_local = to_local(_utc_now_naive(), tz_name).strftime("%Y-%m-%d %H:%M")
    thinking = await message.answer("🤔 Разбираю…")

    try:
        raw = await gemini.parse_text(message.text, tz_name, now_local)
        parsed = parse(raw, tz_name, message.text)
    except NeedsClarification:
        await thinking.edit_text(
            "Не понял, на когда это запланировать. Уточни дату и время — "
            "например: «завтра в 15» или «25.06 в 9:00»."
        )
        return
    except GeminiUnavailable as exc:
        log.warning("gemini unavailable: %r", exc)
        await thinking.edit_text(
            "Сервис распознавания сейчас перегружен 😕 "
            "Попробуй ещё раз через пару секунд."
        )
        return
    except Exception as exc:  # ParseError, кривой JSON и т.п.
        log.warning("free-text parse failed: %r", exc)
        await thinking.edit_text(
            "Не смог разобрать 🤔 Попробуй переформулировать, "
            "например: «завтра в 15 встреча с врачом»."
        )
        return

    await state.update_data(
        draft={
            "title": parsed.title,
            "raw_text": parsed.raw_text,
            "due_at_utc": parsed.due_at_utc.isoformat(),
            "recurrence": parsed.recurrence,
            "recurrence_weekday": parsed.recurrence_weekday,
            "tz_name": tz_name,
        }
    )
    card = _format_card(parsed.title, parsed.due_at_utc, parsed.recurrence, tz_name)
    await thinking.edit_text("Сохранить задачу?\n\n" + card, reply_markup=confirm_kb())


@router.callback_query(F.data == "task:save")
async def on_save(cb: CallbackQuery, state: FSMContext, settings: Settings) -> None:
    draft = (await state.get_data()).get("draft")
    if not draft:
        await cb.answer("Черновик не найден, начни заново.", show_alert=True)
        return

    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session,
            cb.from_user.id,
            cb.from_user.username,
            settings.default_tz,
        )
        await repo.create_task(
            session,
            user_id=user.id,
            title=draft["title"],
            raw_text=draft["raw_text"],
            due_at_utc=datetime.fromisoformat(draft["due_at_utc"]),
            recurrence=draft["recurrence"],
            recurrence_weekday=draft["recurrence_weekday"],
        )
    await state.clear()
    card = _format_card(
        draft["title"],
        datetime.fromisoformat(draft["due_at_utc"]),
        draft["recurrence"],
        draft["tz_name"],
    )
    await cb.message.edit_text("✅ Сохранено:\n\n" + card)
    await cb.answer("Готово")


@router.callback_query(F.data == "task:edit")
async def on_edit(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("Ок, пришли исправленную формулировку задачи 👇")
    await cb.answer()


@router.callback_query(F.data == "task:cancel")
async def on_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("Отменено.")
    await cb.answer()
