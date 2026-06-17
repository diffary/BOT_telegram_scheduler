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


def task_actions_kb(task_id: int) -> InlineKeyboardMarkup:
    """Кнопки действий над сохранённой задачей."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить", callback_data=f"edit:{task_id}"
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить", callback_data=f"del:{task_id}"
                ),
            ]
        ]
    )
