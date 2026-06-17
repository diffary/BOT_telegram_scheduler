from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.utils.tz import to_local, to_utc


def occurrence_on_date(task, day: date) -> datetime | None:
    """Момент (naive UTC) вхождения задачи в указанный UTC-день, либо None.

    Для разовых — только в день due_at_utc. Для повторов — каждый
    подходящий день, в то же время суток, что и due_at_utc.

    Примечание: сравнение идёт по UTC-дате/времени. Для большинства задач
    (время не у полуночи) это совпадает с локальным днём; уточнение под
    локальную зону для weekly у границы суток — задел на будущее.
    """
    tod = task.due_at_utc.time()
    recurrence = task.recurrence

    if recurrence == "none":
        return datetime.combine(day, tod) if task.due_at_utc.date() == day else None
    if recurrence == "daily":
        return datetime.combine(day, tod) if day >= task.due_at_utc.date() else None
    if recurrence == "weekly":
        if day < task.due_at_utc.date():
            return None
        if day.weekday() == task.recurrence_weekday:
            return datetime.combine(day, tod)
        return None
    if recurrence == "monthly":
        if day < task.due_at_utc.date():
            return None
        return datetime.combine(day, tod) if day.day == task.due_at_utc.day else None
    return None


@dataclass
class Occurrence:
    """Одно вхождение задачи для отображения (виртуальное, не строка в БД)."""

    task_id: int
    title: str
    due_at_utc: datetime
    recurrence: str


def _matches_local(task, anchor_local_date: date, day: date) -> bool:
    """Наступает ли задача в локальный день `day` (recurrence в локальной зоне)."""
    recurrence = task.recurrence
    if recurrence == "none":
        return day == anchor_local_date
    if day < anchor_local_date:
        return False
    if recurrence == "daily":
        return True
    if recurrence == "weekly":
        return day.weekday() == task.recurrence_weekday
    if recurrence == "monthly":
        return day.day == anchor_local_date.day
    return False


def expand_occurrences(task, start_date: date, end_date: date, tz_name: str):
    """Вхождения задачи (как occurrence_utc) в локальном диапазоне [start, end].

    Повтор считается в ЛОКАЛЬНОЙ зоне пользователя: weekly по локальному дню
    недели, monthly по локальному числу — так, как имел в виду пользователь.
    """
    original_local = to_local(task.due_at_utc, tz_name)
    anchor_date = original_local.date()
    tod = original_local.time()
    result = []
    day = start_date
    while day <= end_date:
        if _matches_local(task, anchor_date, day):
            result.append(to_utc(datetime.combine(day, tod), tz_name))
        day += timedelta(days=1)
    return result


def build_occurrences(tasks, start_date: date, end_date: date, tz_name: str):
    """Развернуть список задач в отсортированные по времени вхождения (Occurrence)."""
    occurrences = []
    for task in tasks:
        for occ_utc in expand_occurrences(task, start_date, end_date, tz_name):
            occurrences.append(
                Occurrence(task.id, task.title, occ_utc, task.recurrence)
            )
    occurrences.sort(key=lambda o: o.due_at_utc)
    return occurrences


def is_reminder_due(task, now_utc: datetime, default_lead: int) -> bool:
    """Пора ли напомнить о ближайшем вхождении к моменту now_utc.

    Срабатывает в окне [occurrence - lead, occurrence]. Защита от повтора —
    через task.last_reminded_on (один раз в сутки на вхождение).
    """
    if task.last_reminded_on == now_utc.date():
        return False
    occ = occurrence_on_date(task, now_utc.date())
    if occ is None:
        return False
    lead = task.lead_minutes if task.lead_minutes is not None else default_lead
    window_start = occ - timedelta(minutes=lead)
    return window_start <= now_utc <= occ
