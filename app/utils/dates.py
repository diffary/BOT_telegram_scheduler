import re
from datetime import date, timedelta

_DDMM = re.compile(r"(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?")


def parse_date_arg(arg: str, today: date) -> tuple[date, date, str]:
    """Разобрать аргумент команды /list в диапазон дат.

    Возвращает (start_date, end_date, label) — границы включительные.
    Поддерживает: пусто/сегодня, завтра, послезавтра, вчера, неделя,
    а также ДД.ММ и ДД.ММ.ГГГГ.

    Бросает ValueError, если не распознал.
    """
    a = (arg or "").strip().lower()

    if a in ("", "сегодня", "today"):
        return today, today, "Сегодня"
    if a in ("завтра", "tomorrow"):
        d = today + timedelta(days=1)
        return d, d, "Завтра"
    if a == "послезавтра":
        d = today + timedelta(days=2)
        return d, d, "Послезавтра"
    if a in ("вчера", "yesterday"):
        d = today - timedelta(days=1)
        return d, d, "Вчера"
    if a in ("неделя", "week", "на неделю"):
        return today, today + timedelta(days=6), "Неделя"

    m = _DDMM.fullmatch(a)
    if m:
        day = int(m.group(1))
        month = int(m.group(2))
        year_part = m.group(3)
        if year_part:
            year = int(year_part)
            if year < 100:
                year += 2000
        else:
            year = today.year
        try:
            d = date(year, month, day)
        except ValueError as exc:
            raise ValueError(f"некорректная дата: {arg!r}") from exc
        return d, d, d.strftime("%d.%m.%Y")

    raise ValueError(f"не понял дату: {arg!r}")
