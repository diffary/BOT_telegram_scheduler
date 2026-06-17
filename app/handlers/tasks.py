import logging
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.db import repo
from app.db.base import get_sessionmaker
from app.keyboards.inline import confirm_kb, task_actions_kb
from app.services.gemini import GeminiService, GeminiUnavailable
from app.services.parser import NeedsClarification, parse
from app.states import EditTask
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


async def _resolve_user(tg_user, settings: Settings):
    """Найти/создать пользователя, вернуть (user_id, tz_name)."""
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, tg_user.id, tg_user.username, settings.default_tz
        )
        return user.id, user.timezone


def _now_local_str(tz_name: str) -> str:
    return to_local(_utc_now_naive(), tz_name).strftime("%Y-%m-%d %H:%M")


async def _safe_parse(raw_awaitable, tz_name: str, raw_text: str):
    """Дождаться сырой dict от Gemini и распарсить.

    Вернуть (ParsedTask|None, error_message|None). Единая обработка ошибок
    для создания и редактирования.
    """
    try:
        raw = await raw_awaitable
        return parse(raw, tz_name, raw_text), None
    except NeedsClarification:
        return None, (
            "Не понял, на когда это запланировать. Уточни дату и время — "
            "например: «завтра в 15» или «25.06 в 9:00»."
        )
    except GeminiUnavailable as exc:
        log.warning("gemini unavailable: %r", exc)
        return None, (
            "Сервис распознавания сейчас перегружен 😕 "
            "Попробуй ещё раз через пару секунд."
        )
    except Exception as exc:  # ParseError, кривой JSON и т.п.
        log.warning("parse failed: %r", exc)
        return None, (
            "Не смог разобрать 🤔 Попробуй переформулировать, "
            "например: «завтра в 15 встреча с врачом»."
        )


# --- создание задачи (свободный текст в обычном состоянии) ---

@router.message(StateFilter(None), F.text & ~F.text.startswith("/"))
async def on_free_text(
    message: Message,
    state: FSMContext,
    gemini: GeminiService,
    settings: Settings,
) -> None:
    _, tz_name = await _resolve_user(message.from_user, settings)
    thinking = await message.answer("🤔 Разбираю…")

    raw = gemini.parse_text(message.text, tz_name, _now_local_str(tz_name))
    parsed, error = await _safe_parse(raw, tz_name, message.text)
    if error:
        await thinking.edit_text(error)
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
            session, cb.from_user.id, cb.from_user.username, settings.default_tz
        )
        task = await repo.create_task(
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
    await cb.message.edit_text(
        "✅ Сохранено:\n\n" + card, reply_markup=task_actions_kb(task.id)
    )
    await cb.answer("Готово")


@router.callback_query(F.data == "task:edit")
async def on_draft_edit(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("Ок, пришли исправленную формулировку задачи 👇")
    await cb.answer()


@router.callback_query(F.data == "task:cancel")
async def on_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.edit_text("Отменено.")
    await cb.answer()


# --- удаление ---

@router.callback_query(F.data.startswith("del:"))
async def on_delete(cb: CallbackQuery, settings: Settings) -> None:
    task_id = int(cb.data.split(":")[1])
    user_id, _ = await _resolve_user(cb.from_user, settings)
    maker = get_sessionmaker()
    async with maker() as session:
        await repo.delete_task(session, task_id, user_id)
    await cb.message.edit_text("🗑 Задача удалена.")
    await cb.answer("Удалено")


# --- редактирование ---

@router.callback_query(F.data.startswith("edit:"))
async def on_edit_request(
    cb: CallbackQuery, state: FSMContext, settings: Settings
) -> None:
    task_id = int(cb.data.split(":")[1])
    user_id, _ = await _resolve_user(cb.from_user, settings)
    maker = get_sessionmaker()
    async with maker() as session:
        task = await repo.get_task(session, task_id, user_id)
    if task is None:
        await cb.answer("Задача не найдена.", show_alert=True)
        return

    await state.set_state(EditTask.waiting_text)
    await state.update_data(edit_task_id=task_id)
    await cb.message.answer(
        "✏️ Что изменить? Можно дописать («и ещё помыть собаку»), "
        "перенести время («перенеси на 18:00») или переформулировать целиком. "
        "/cancel — отмена."
    )
    await cb.answer()


@router.message(EditTask.waiting_text, F.text & ~F.text.startswith("/"))
async def on_edit_text(
    message: Message,
    state: FSMContext,
    gemini: GeminiService,
    settings: Settings,
) -> None:
    task_id = (await state.get_data()).get("edit_task_id")
    user_id, tz_name = await _resolve_user(message.from_user, settings)

    maker = get_sessionmaker()
    async with maker() as session:
        task = await repo.get_task(session, task_id, user_id)
    if task is None:
        await state.clear()
        await message.answer("Задача не найдена 🤔")
        return

    thinking = await message.answer("🤔 Разбираю…")

    # передаём исходную задачу как контекст, чтобы дополнения/правки
    # опирались на неё, а не парсились с нуля
    current = {
        "title": task.title,
        "datetime_local": to_local(task.due_at_utc, tz_name).strftime("%Y-%m-%d %H:%M"),
        "recurrence": task.recurrence,
        "weekday": task.recurrence_weekday,
    }
    raw = gemini.amend_text(message.text, current, tz_name, _now_local_str(tz_name))
    parsed, error = await _safe_parse(raw, tz_name, message.text)
    if error:
        # остаёмся в режиме редактирования — можно прислать ещё раз
        await thinking.edit_text(error)
        return

    maker = get_sessionmaker()
    async with maker() as session:
        updated = await repo.update_task(
            session,
            task_id,
            user_id,
            title=parsed.title,
            raw_text=parsed.raw_text,
            due_at_utc=parsed.due_at_utc,
            recurrence=parsed.recurrence,
            recurrence_weekday=parsed.recurrence_weekday,
        )
    await state.clear()
    if updated is None:
        await thinking.edit_text("Задача не найдена 🤔")
        return

    card = _format_card(parsed.title, parsed.due_at_utc, parsed.recurrence, tz_name)
    await thinking.edit_text(
        "✏️ Обновлено:\n\n" + card, reply_markup=task_actions_kb(task_id)
    )
