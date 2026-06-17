from datetime import datetime

import pytest

from app.services.parser import (
    NeedsClarification,
    ParseError,
    ParsedTask,
    parse,
)


def test_parse_one_off_converts_moscow_to_utc():
    raw = {
        "title": "встреча с врачом",
        "datetime_local": "2026-06-17 15:00",
        "recurrence": "none",
        "weekday": None,
    }
    result = parse(raw, tz_name="Europe/Moscow", raw_text="завтра в 15 врач")
    assert isinstance(result, ParsedTask)
    assert result.title == "встреча с врачом"
    assert result.recurrence == "none"
    assert result.recurrence_weekday is None
    # 15:00 MSK (UTC+3) -> 12:00 UTC, хранится naive
    assert result.due_at_utc == datetime(2026, 6, 17, 12, 0)
    assert result.due_at_utc.tzinfo is None


def test_parse_converts_other_timezone():
    raw = {"title": "x", "datetime_local": "2026-06-17 09:00", "recurrence": "none"}
    # Asia/Almaty = UTC+5 -> 04:00 UTC
    result = parse(raw, tz_name="Asia/Almaty", raw_text="r")
    assert result.due_at_utc == datetime(2026, 6, 17, 4, 0)


def test_parse_weekly_keeps_weekday():
    raw = {
        "title": "планёрка",
        "datetime_local": "2026-06-17 10:00",
        "recurrence": "weekly",
        "weekday": 2,
    }
    result = parse(raw, tz_name="Europe/Moscow", raw_text="r")
    assert result.recurrence == "weekly"
    assert result.recurrence_weekday == 2


def test_parse_weekday_ignored_when_not_weekly():
    raw = {
        "title": "x",
        "datetime_local": "2026-06-17 10:00",
        "recurrence": "daily",
        "weekday": 3,
    }
    result = parse(raw, tz_name="Europe/Moscow", raw_text="r")
    assert result.recurrence == "daily"
    assert result.recurrence_weekday is None


def test_parse_invalid_weekday_becomes_none():
    raw = {
        "title": "x",
        "datetime_local": "2026-06-17 10:00",
        "recurrence": "weekly",
        "weekday": 99,
    }
    result = parse(raw, tz_name="Europe/Moscow", raw_text="r")
    assert result.recurrence_weekday is None


def test_parse_null_datetime_needs_clarification():
    raw = {"title": "купить молоко", "datetime_local": None, "recurrence": "none"}
    with pytest.raises(NeedsClarification):
        parse(raw, tz_name="Europe/Moscow", raw_text="купить молоко")


def test_parse_missing_datetime_needs_clarification():
    raw = {"title": "купить молоко", "recurrence": "none"}
    with pytest.raises(NeedsClarification):
        parse(raw, tz_name="Europe/Moscow", raw_text="r")


def test_needs_clarification_is_parse_error_subclass():
    # хендлер ловит NeedsClarification отдельно, но это всё ещё ParseError
    assert issubclass(NeedsClarification, ParseError)


def test_parse_missing_title_raises():
    raw = {"datetime_local": "2026-06-17 15:00", "recurrence": "none"}
    with pytest.raises(ParseError):
        parse(raw, tz_name="Europe/Moscow", raw_text="r")


def test_parse_bad_datetime_format_raises():
    raw = {"title": "x", "datetime_local": "17 июня в 3 часа", "recurrence": "none"}
    with pytest.raises(ParseError):
        parse(raw, tz_name="Europe/Moscow", raw_text="r")


def test_parse_unknown_recurrence_defaults_to_none():
    raw = {"title": "x", "datetime_local": "2026-06-17 15:00", "recurrence": "yearly"}
    result = parse(raw, tz_name="Europe/Moscow", raw_text="r")
    assert result.recurrence == "none"


def test_parse_non_dict_raises():
    with pytest.raises(ParseError):
        parse("not a dict", tz_name="Europe/Moscow", raw_text="r")
