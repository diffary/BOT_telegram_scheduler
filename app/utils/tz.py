from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

_UTC = ZoneInfo("UTC")
_AVAILABLE = available_timezones()


def is_valid_tz(name: str) -> bool:
    """Проверить, что строка — корректная IANA-зона (например Europe/Moscow)."""
    return name in _AVAILABLE


def to_utc(local_naive: datetime, tz_name: str) -> datetime:
    """Локальное naive-время в зоне tz_name -> naive UTC (для хранения в БД)."""
    aware = local_naive.replace(tzinfo=ZoneInfo(tz_name))
    return aware.astimezone(_UTC).replace(tzinfo=None)


def to_local(utc_naive: datetime, tz_name: str) -> datetime:
    """naive UTC -> локальное naive-время в зоне tz_name (для отображения)."""
    aware = utc_naive.replace(tzinfo=_UTC)
    return aware.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None)
