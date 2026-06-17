import logging

from aiogram import Router
from aiogram.types import ErrorEvent

log = logging.getLogger(__name__)
router = Router()


@router.errors()
async def on_error(event: ErrorEvent) -> bool:
    """Ловит любое непойманное исключение в хендлерах: логирует и мягко
    уведомляет пользователя, чтобы бот не «молчал» при сбое."""
    log.exception("Unhandled update error: %r", event.exception)
    update = event.update
    try:
        if update.message:
            await update.message.answer(
                "Упс, что-то пошло не так 🙈 Попробуй ещё раз."
            )
        elif update.callback_query:
            await update.callback_query.answer(
                "Что-то пошло не так, попробуй ещё раз.", show_alert=True
            )
    except Exception:
        log.exception("failed to notify user about error")
    return True
