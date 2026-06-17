from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Популярные часовые пояса для быстрого выбора.
POPULAR_TZ = [
    ("🇺🇦 Київ", "Europe/Kyiv"),
    ("🇷🇺 Москва", "Europe/Moscow"),
    ("🇰🇿 Алмати", "Asia/Almaty"),
    ("🇧🇾 Мінськ", "Europe/Minsk"),
    ("🇵🇱 Варшава", "Europe/Warsaw"),
    ("🇩🇪 Берлін", "Europe/Berlin"),
    ("🇬🇪 Тбілісі", "Asia/Tbilisi"),
    ("🇬🇧 Лондон", "Europe/London"),
]


def timezone_kb() -> InlineKeyboardMarkup:
    """Кнопки популярных зон (по 2 в ряд) + ручной ввод."""
    rows = []
    for i in range(0, len(POPULAR_TZ), 2):
        row = [
            InlineKeyboardButton(text=label, callback_data=f"tz:set:{tz}")
            for label, tz in POPULAR_TZ[i:i + 2]
        ]
        rows.append(row)
    rows.append(
        [InlineKeyboardButton(text="✍️ Ввести вручную", callback_data="tz:manual")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_kb(digest_enabled: bool) -> InlineKeyboardMarkup:
    """Кнопки управления настройками."""
    toggle = "🔔 Дайджест: ВКЛ" if digest_enabled else "🔕 Дайджест: ВЫКЛ"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle, callback_data="set:digest_toggle")],
            [InlineKeyboardButton(text="🕘 Время дайджеста", callback_data="set:digest_time")],
            [InlineKeyboardButton(text="⏰ Когда напоминать", callback_data="set:lead")],
            [InlineKeyboardButton(text="🌍 Часовой пояс", callback_data="set:tz")],
        ]
    )


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
