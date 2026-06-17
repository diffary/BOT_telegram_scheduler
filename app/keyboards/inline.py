from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def confirm_kb() -> InlineKeyboardMarkup:
    """Кнопки подтверждения создания задачи."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Сохранить", callback_data="task:save"),
                InlineKeyboardButton(text="✏️ Изменить", callback_data="task:edit"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="task:cancel"),
            ]
        ]
    )
