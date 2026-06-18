from datetime import datetime

from app.utils.tz import resolve_timezone, to_local, to_utc


# --- конвертация ---

def test_to_utc_moscow():
    # 15:00 MSK (UTC+3) -> 12:00 UTC
    assert to_utc(datetime(2026, 6, 18, 15, 0), "Europe/Moscow") == datetime(2026, 6, 18, 12, 0)


def test_to_local_roundtrip():
    assert to_local(datetime(2026, 6, 18, 12, 0), "Europe/Moscow") == datetime(2026, 6, 18, 15, 0)


# --- resolve_timezone: точный IANA ---

def test_resolve_exact_iana():
    assert resolve_timezone("Europe/Moscow") == "Europe/Moscow"


# --- город ---

def test_resolve_city_novosibirsk():
    assert resolve_timezone("Новосибирск") == "Asia/Novosibirsk"


def test_resolve_city_case_insensitive():
    assert resolve_timezone("  киев ") == "Europe/Kyiv"


def test_resolve_city_almaty_alias():
    assert resolve_timezone("алма-ата") == "Asia/Almaty"


# --- сдвиг от UTC ---

def test_resolve_offset_plus_7():
    # Etc/GMT-7 == UTC+7 (знак инвертирован)
    tz = resolve_timezone("+7")
    assert tz == "Etc/GMT-7"
    # сверим, что это действительно UTC+7: 10:00 локально -> 03:00 UTC
    assert to_utc(datetime(2026, 6, 18, 10, 0), tz) == datetime(2026, 6, 18, 3, 0)


def test_resolve_offset_minus_3():
    assert resolve_timezone("-3") == "Etc/GMT+3"


def test_resolve_offset_zero_is_utc():
    assert resolve_timezone("0") == "UTC"


def test_resolve_offset_with_utc_prefix():
    assert resolve_timezone("UTC+5") == "Etc/GMT-5"


# --- мусор ---

def test_resolve_unknown_returns_none():
    assert resolve_timezone("абвгд") is None
    assert resolve_timezone("") is None
    assert resolve_timezone("+99") is None  # вне диапазона
