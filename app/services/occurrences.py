from datetime import date, datetime, timedelta


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
