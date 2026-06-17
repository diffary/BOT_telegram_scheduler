from datetime import date, datetime

from app.services.occurrences import (
    build_occurrences,
    expand_occurrences,
    is_reminder_due,
    occurrence_on_date,
)


class FakeTask:
    def __init__(self, due_at_utc, recurrence="none", weekday=None,
                 lead=15, last=None, id=1, title="t"):
        self.id = id
        self.title = title
        self.due_at_utc = due_at_utc
        self.recurrence = recurrence
        self.recurrence_weekday = weekday
        self.lead_minutes = lead
        self.last_reminded_on = last


# --- occurrence_on_date ---

def test_one_off_only_on_its_date():
    t = FakeTask(datetime(2026, 6, 17, 12, 0))
    assert occurrence_on_date(t, date(2026, 6, 17)) == datetime(2026, 6, 17, 12, 0)
    assert occurrence_on_date(t, date(2026, 6, 18)) is None


def test_daily_every_day_same_time():
    t = FakeTask(datetime(2026, 6, 17, 8, 0), recurrence="daily")
    assert occurrence_on_date(t, date(2026, 6, 20)) == datetime(2026, 6, 20, 8, 0)
    # раньше стартовой даты — нет
    assert occurrence_on_date(t, date(2026, 6, 16)) is None


def test_weekly_only_matching_weekday():
    # 2026-06-17 — среда (weekday=2)
    t = FakeTask(datetime(2026, 6, 17, 9, 0), recurrence="weekly", weekday=2)
    assert occurrence_on_date(t, date(2026, 6, 24)) == datetime(2026, 6, 24, 9, 0)
    assert occurrence_on_date(t, date(2026, 6, 25)) is None


def test_monthly_same_day_of_month():
    t = FakeTask(datetime(2026, 6, 17, 9, 0), recurrence="monthly")
    assert occurrence_on_date(t, date(2026, 7, 17)) == datetime(2026, 7, 17, 9, 0)
    assert occurrence_on_date(t, date(2026, 7, 18)) is None


# --- is_reminder_due ---

def test_due_inside_lead_window():
    t = FakeTask(datetime(2026, 6, 17, 12, 0), lead=15)
    # окно открылось в 11:45
    assert is_reminder_due(t, datetime(2026, 6, 17, 11, 45), 15) is True
    assert is_reminder_due(t, datetime(2026, 6, 17, 11, 50), 15) is True


def test_not_due_before_window():
    t = FakeTask(datetime(2026, 6, 17, 12, 0), lead=15)
    assert is_reminder_due(t, datetime(2026, 6, 17, 11, 30), 15) is False


def test_not_resent_same_day():
    t = FakeTask(datetime(2026, 6, 17, 12, 0), lead=15, last=date(2026, 6, 17))
    assert is_reminder_due(t, datetime(2026, 6, 17, 11, 50), 15) is False


def test_uses_default_lead_when_none():
    t = FakeTask(datetime(2026, 6, 17, 12, 0), lead=None)
    assert is_reminder_due(t, datetime(2026, 6, 17, 11, 35), 30) is True
    assert is_reminder_due(t, datetime(2026, 6, 17, 11, 25), 30) is False


# --- expand_occurrences (раскрытие повторов для просмотра, локальная зона) ---

TZ = "Europe/Moscow"  # UTC+3


def test_expand_none_only_anchor_day():
    # 07:00 UTC = 10:00 MSK, разовая
    t = FakeTask(datetime(2026, 6, 17, 7, 0), recurrence="none")
    occ = expand_occurrences(t, date(2026, 6, 15), date(2026, 6, 20), TZ)
    assert occ == [datetime(2026, 6, 17, 7, 0)]


def test_expand_daily_every_day_in_range():
    t = FakeTask(datetime(2026, 6, 15, 7, 0), recurrence="daily")
    occ = expand_occurrences(t, date(2026, 6, 17), date(2026, 6, 19), TZ)
    assert occ == [
        datetime(2026, 6, 17, 7, 0),
        datetime(2026, 6, 18, 7, 0),
        datetime(2026, 6, 19, 7, 0),
    ]


def test_expand_weekly_only_matching_weekday():
    # 2026-06-17 — среда (локально); weekday=2
    t = FakeTask(datetime(2026, 6, 17, 7, 0), recurrence="weekly", weekday=2)
    occ = expand_occurrences(t, date(2026, 6, 18), date(2026, 6, 24), TZ)
    assert occ == [datetime(2026, 6, 24, 7, 0)]  # следующая среда


def test_expand_monthly_same_day_number():
    t = FakeTask(datetime(2026, 6, 17, 7, 0), recurrence="monthly")
    occ = expand_occurrences(t, date(2026, 7, 1), date(2026, 7, 31), TZ)
    assert occ == [datetime(2026, 7, 17, 7, 0)]


def test_expand_skips_before_anchor():
    t = FakeTask(datetime(2026, 6, 17, 7, 0), recurrence="daily")
    occ = expand_occurrences(t, date(2026, 6, 10), date(2026, 6, 16), TZ)
    assert occ == []


def test_build_occurrences_sorts_and_flattens():
    daily = FakeTask(datetime(2026, 6, 15, 9, 0), recurrence="daily",
                     id=1, title="зарядка")
    one_off = FakeTask(datetime(2026, 6, 17, 6, 0), recurrence="none",
                       id=2, title="врач")
    occ = build_occurrences([daily, one_off], date(2026, 6, 17), date(2026, 6, 17), TZ)
    # оба попадают на 17-е; сортировка по времени: врач 06:00 < зарядка 09:00
    assert [o.title for o in occ] == ["врач", "зарядка"]
    assert all(o.due_at_utc.date() == date(2026, 6, 17) for o in occ)
