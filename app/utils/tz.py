import re
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

_UTC = ZoneInfo("UTC")
_AVAILABLE = available_timezones()

# Город (в нижнем регистре) -> IANA-зона. Покрывает частые СНГ/ЕС города.
_CITY_TZ = {
    # Россия
    "москва": "Europe/Moscow", "мск": "Europe/Moscow", "moscow": "Europe/Moscow",
    "санкт-петербург": "Europe/Moscow", "спб": "Europe/Moscow",
    "питер": "Europe/Moscow", "петербург": "Europe/Moscow",
    "казань": "Europe/Moscow", "нижний новгород": "Europe/Moscow",
    "ростов": "Europe/Moscow", "ростов-на-дону": "Europe/Moscow",
    "сочи": "Europe/Moscow", "краснодар": "Europe/Moscow",
    "калининград": "Europe/Kaliningrad",
    "самара": "Europe/Samara", "ижевск": "Europe/Samara",
    "екатеринбург": "Asia/Yekaterinburg", "челябинск": "Asia/Yekaterinburg",
    "уфа": "Asia/Yekaterinburg", "пермь": "Asia/Yekaterinburg",
    "омск": "Asia/Omsk",
    "новосибирск": "Asia/Novosibirsk", "новосиб": "Asia/Novosibirsk",
    "красноярск": "Asia/Krasnoyarsk", "барнаул": "Asia/Barnaul",
    "иркутск": "Asia/Irkutsk",
    "якутск": "Asia/Yakutsk", "чита": "Asia/Chita",
    "владивосток": "Asia/Vladivostok", "хабаровск": "Asia/Vladivostok",
    "магадан": "Asia/Magadan",
    "камчатка": "Asia/Kamchatka", "петропавловск-камчатский": "Asia/Kamchatka",
    # Украина / Беларусь / Молдова
    "киев": "Europe/Kyiv", "київ": "Europe/Kyiv", "kyiv": "Europe/Kyiv",
    "kiev": "Europe/Kyiv", "харьков": "Europe/Kyiv", "одесса": "Europe/Kyiv",
    "львов": "Europe/Kyiv", "днепр": "Europe/Kyiv", "запорожье": "Europe/Kyiv",
    "минск": "Europe/Minsk", "minsk": "Europe/Minsk",
    "кишинёв": "Europe/Chisinau", "кишинев": "Europe/Chisinau",
    # Кавказ / Средняя Азия
    "тбилиси": "Asia/Tbilisi", "ереван": "Asia/Yerevan", "баку": "Asia/Baku",
    "алматы": "Asia/Almaty", "алма-ата": "Asia/Almaty", "almaty": "Asia/Almaty",
    "астана": "Asia/Almaty", "нур-султан": "Asia/Almaty",
    "ташкент": "Asia/Tashkent", "бишкек": "Asia/Bishkek",
    # Европа
    "варшава": "Europe/Warsaw", "берлин": "Europe/Berlin", "лондон": "Europe/London",
    "париж": "Europe/Paris", "прага": "Europe/Prague", "рим": "Europe/Rome",
    "мадрид": "Europe/Madrid", "амстердам": "Europe/Amsterdam",
    "вильнюс": "Europe/Vilnius", "рига": "Europe/Riga", "таллин": "Europe/Tallinn",
    "стамбул": "Europe/Istanbul",
    # Америка
    "нью-йорк": "America/New_York", "new york": "America/New_York",
    "лос-анджелес": "America/Los_Angeles",
}

_OFFSET_RE = re.compile(r"(?:utc|gmt|мск)?([+-]?\d{1,2})(?::?00)?")


def is_valid_tz(name: str) -> bool:
    """Проверить, что строка — корректная IANA-зона (например Europe/Moscow)."""
    return name in _AVAILABLE


def resolve_timezone(text: str) -> str | None:
    """Распознать часовой пояс из свободного ввода: точный IANA, город или
    сдвиг от UTC ("+7", "-3", "utc+5"). Вернуть IANA-имя или None.
    """
    raw = (text or "").strip()
    if not raw:
        return None

    # 1) уже корректный IANA ("Europe/Moscow")
    if is_valid_tz(raw):
        return raw

    # 2) сдвиг от UTC: "+7", "-3", "utc+5", "+7:00"
    compact = raw.lower().replace(" ", "")
    m = _OFFSET_RE.fullmatch(compact)
    if m:
        offset = int(m.group(1))
        if -12 <= offset <= 14:
            if offset == 0:
                return "UTC"
            # У Etc/GMT знак инвертирован: Etc/GMT-7 == UTC+7
            name = f"Etc/GMT{'-' if offset > 0 else '+'}{abs(offset)}"
            if is_valid_tz(name):
                return name

    # 3) город
    return _CITY_TZ.get(raw.lower())


def to_utc(local_naive: datetime, tz_name: str) -> datetime:
    """Локальное naive-время в зоне tz_name -> naive UTC (для хранения в БД)."""
    aware = local_naive.replace(tzinfo=ZoneInfo(tz_name))
    return aware.astimezone(_UTC).replace(tzinfo=None)


def to_local(utc_naive: datetime, tz_name: str) -> datetime:
    """naive UTC -> локальное naive-время в зоне tz_name (для отображения)."""
    aware = utc_naive.replace(tzinfo=_UTC)
    return aware.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None)
