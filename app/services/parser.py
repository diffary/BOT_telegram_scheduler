from dataclasses import dataclass
from datetime import datetime

from app.utils.tz import to_utc

VALID_RECURRENCE = {"none", "daily", "weekly", "monthly"}
_DATETIME_FORMAT = "%Y-%m-%d %H:%M"


class ParseError(ValueError):
    """Ответ Gemini структурно невалиден и не может быть разобран."""


class NeedsClarification(ParseError):
    """Пользователь не указал дату/время явно — нужно переспросить, не угадывать."""


@dataclass
class ParsedTask:
    title: str
    raw_text: str
    due_at_utc: datetime
    recurrence: str
    recurrence_weekday: int | None


def parse(raw: dict, tz_name: str, raw_text: str) -> ParsedTask:
    """Провалидировать ответ Gemini и собрать ParsedTask с временем в UTC.

    Бросает:
      - NeedsClarification — если дата/время не указаны (datetime_local пустой/null);
      - ParseError — если структура/формат ответа некорректны.
    """
    if not isinstance(raw, dict):
        raise ParseError("ожидался JSON-объект")

    title = (raw.get("title") or "").strip()
    if not title:
        raise ParseError("отсутствует поле title")

    dt_str = raw.get("datetime_local")
    # Gemini по промпту обязан вернуть null, если время не задано явно.
    if dt_str in (None, "", "null", "none"):
        raise NeedsClarification("дата/время не указаны")

    try:
        local_dt = datetime.strptime(dt_str, _DATETIME_FORMAT)
    except (ValueError, TypeError) as exc:
        raise ParseError(f"неверный формат datetime_local: {dt_str!r}") from exc

    recurrence = raw.get("recurrence") or "none"
    if recurrence not in VALID_RECURRENCE:
        recurrence = "none"

    weekday = _normalize_weekday(raw.get("weekday")) if recurrence == "weekly" else None

    return ParsedTask(
        title=title,
        raw_text=raw_text,
        due_at_utc=to_utc(local_dt, tz_name),
        recurrence=recurrence,
        recurrence_weekday=weekday,
    )


def _normalize_weekday(value) -> int | None:
    if value is None:
        return None
    try:
        weekday = int(value)
    except (ValueError, TypeError):
        return None
    return weekday if 0 <= weekday <= 6 else None
