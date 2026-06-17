from datetime import datetime

from app.utils.formatting import (
    format_day_list,
    format_day_sections,
    format_grouped_by_day,
    format_task_line,
    recurrence_label,
)


class FakeTask:
    def __init__(self, title, due_at_utc, recurrence="none"):
        self.title = title
        self.due_at_utc = due_at_utc
        self.recurrence = recurrence


def test_recurrence_label():
    assert recurrence_label("none") == ""
    assert "ежедневно" in recurrence_label("daily")
    assert "еженедельно" in recurrence_label("weekly")
    assert "ежемесячно" in recurrence_label("monthly")


def test_format_task_line_shows_local_time():
    # 12:00 UTC -> 15:00 MSK
    t = FakeTask("врач", datetime(2026, 6, 17, 12, 0))
    line = format_task_line(t, "Europe/Moscow")
    assert "15:00" in line
    assert "врач" in line


def test_format_task_line_includes_recurrence():
    t = FakeTask("планёрка", datetime(2026, 6, 17, 7, 0), recurrence="weekly")
    line = format_task_line(t, "Europe/Moscow")
    assert "еженедельно" in line


def test_format_day_list_empty_is_friendly():
    out = format_day_list([], "Europe/Moscow", "📅 Сегодня")
    assert "📅 Сегодня" in out
    assert "свободно" in out.lower()


def test_format_day_list_with_tasks():
    tasks = [
        FakeTask("ранняя", datetime(2026, 6, 17, 6, 0)),
        FakeTask("поздняя", datetime(2026, 6, 17, 15, 0)),
    ]
    out = format_day_list(tasks, "Europe/Moscow", "📅 Сегодня")
    assert "ранняя" in out and "поздняя" in out


def test_format_grouped_by_day_groups_dates():
    tasks = [
        FakeTask("день1", datetime(2026, 6, 17, 9, 0)),
        FakeTask("день2", datetime(2026, 6, 18, 9, 0)),
    ]
    out = format_grouped_by_day(tasks, "Europe/Moscow", "📅 Неделя")
    # обе локальные даты как подзаголовки
    assert "17.06" in out and "18.06" in out
    assert "день1" in out and "день2" in out


def test_format_grouped_empty():
    out = format_grouped_by_day([], "Europe/Moscow", "📅 Неделя")
    assert "свободно" in out.lower()


# --- секции «Предстоит / Прошло» ---

def test_sections_split_past_and_upcoming():
    now = datetime(2026, 6, 17, 11, 0)  # UTC
    tasks = [
        FakeTask("прошедшая", datetime(2026, 6, 17, 9, 0)),
        FakeTask("будущая", datetime(2026, 6, 17, 15, 0)),
    ]
    out = format_day_sections(tasks, "Europe/Moscow", "📅 Сегодня", now)
    assert "Предстоит" in out and "Прошло" in out
    # «Предстоит» идёт раньше «Прошло»
    assert out.index("Предстоит") < out.index("Прошло")
    assert "будущая" in out and "прошедшая" in out


def test_sections_all_upcoming_no_past_block():
    now = datetime(2026, 6, 17, 8, 0)
    tasks = [FakeTask("будущая", datetime(2026, 6, 17, 15, 0))]
    out = format_day_sections(tasks, "Europe/Moscow", "📅 Сегодня", now)
    assert "Предстоит" in out
    assert "Прошло" not in out


def test_sections_all_past_no_upcoming_block():
    now = datetime(2026, 6, 17, 20, 0)
    tasks = [FakeTask("давняя", datetime(2026, 6, 17, 9, 0))]
    out = format_day_sections(tasks, "Europe/Moscow", "📅 Сегодня", now)
    assert "Прошло" in out
    assert "Предстоит" not in out


def test_sections_empty_friendly():
    out = format_day_sections([], "Europe/Moscow", "📅 Сегодня", datetime(2026, 6, 17, 12, 0))
    assert "свободно" in out.lower()
