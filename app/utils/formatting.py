from collections import OrderedDict

from app.utils.tz import to_local

_REC_LABEL = {
    "none": "",
    "daily": "🔁 ежедневно",
    "weekly": "📅 еженедельно",
    "monthly": "🗓 ежемесячно",
}

_RU_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def recurrence_label(recurrence: str) -> str:
    """Подпись для типа повтора (пустая строка для разовых)."""
    return _REC_LABEL.get(recurrence, "")


def format_task_line(task, tz_name: str, icon: str = "🕒") -> str:
    """Одна строка задачи: локальное время — заголовок (+ повтор)."""
    local = to_local(task.due_at_utc, tz_name)
    label = recurrence_label(getattr(task, "recurrence", "none"))
    suffix = f"  · {label}" if label else ""
    return f"{icon} {local:%H:%M} — {task.title}{suffix}"


def format_day_list(tasks, tz_name: str, header: str) -> str:
    """Список задач на один день (или дружелюбное сообщение, если пусто)."""
    if not tasks:
        return f"{header}\n\nНа этот день задач нет — свободно 🎉"
    lines = "\n".join(format_task_line(t, tz_name) for t in tasks)
    return f"{header}\n\n{lines}"


def format_day_sections(tasks, tz_name: str, header: str, now_utc) -> str:
    """Список задач на один день, разделённый на «Предстоит» и «Прошло»
    относительно момента now_utc. Пустой день — дружелюбное сообщение.
    """
    if not tasks:
        return f"{header}\n\nНа этот день задач нет — свободно 🎉"

    upcoming = [t for t in tasks if t.due_at_utc >= now_utc]
    past = [t for t in tasks if t.due_at_utc < now_utc]

    parts = [header]
    if upcoming:
        lines = "\n".join(format_task_line(t, tz_name) for t in upcoming)
        parts.append(f"⏳ Предстоит:\n{lines}")
    if past:
        lines = "\n".join(format_task_line(t, tz_name, icon="✔️") for t in past)
        parts.append(f"✔️ Прошло:\n{lines}")
    return "\n\n".join(parts)


def format_grouped_by_day(tasks, tz_name: str, header: str) -> str:
    """Список задач за несколько дней, сгруппированный по локальной дате."""
    if not tasks:
        return f"{header}\n\nЗадач нет — свободно 🎉"

    groups: "OrderedDict[object, list]" = OrderedDict()
    for task in tasks:
        day = to_local(task.due_at_utc, tz_name).date()
        groups.setdefault(day, []).append(task)

    blocks = []
    for day, items in groups.items():
        day_header = f"📌 {day:%d.%m} ({_RU_WEEKDAYS[day.weekday()]})"
        lines = "\n".join(format_task_line(t, tz_name) for t in items)
        blocks.append(f"{day_header}\n{lines}")

    return f"{header}\n\n" + "\n\n".join(blocks)
