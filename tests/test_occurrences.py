from datetime import date, datetime

from app.services.occurrences import is_reminder_due, occurrence_on_date


class FakeTask:
    def __init__(self, due_at_utc, recurrence="none", weekday=None,
                 lead=15, last=None):
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
