from datetime import date

import pytest

from app.utils.dates import parse_date_arg

TODAY = date(2026, 6, 17)  # среда


def test_empty_is_today():
    assert parse_date_arg("", TODAY) == (TODAY, TODAY, "Сегодня")


def test_segodnya():
    assert parse_date_arg("сегодня", TODAY)[0] == TODAY


def test_zavtra():
    s, e, label = parse_date_arg("завтра", TODAY)
    assert s == e == date(2026, 6, 18)
    assert label == "Завтра"


def test_poslezavtra():
    s, e, _ = parse_date_arg("послезавтра", TODAY)
    assert s == e == date(2026, 6, 19)


def test_vchera():
    s, e, _ = parse_date_arg("вчера", TODAY)
    assert s == e == date(2026, 6, 16)


def test_nedelya_is_range():
    s, e, label = parse_date_arg("неделя", TODAY)
    assert s == TODAY
    assert e == date(2026, 6, 23)
    assert label == "Неделя"


def test_ddmm_uses_current_year():
    s, e, label = parse_date_arg("20.06", TODAY)
    assert s == e == date(2026, 6, 20)
    assert label == "20.06.2026"


def test_ddmmyyyy():
    s, e, _ = parse_date_arg("01.01.2027", TODAY)
    assert s == e == date(2027, 1, 1)


def test_ddmm_two_digit_year():
    s, _, _ = parse_date_arg("15.03.27", TODAY)
    assert s == date(2027, 3, 15)


def test_case_insensitive_and_spaces():
    assert parse_date_arg("  ЗАВТРА  ", TODAY)[0] == date(2026, 6, 18)


def test_invalid_date_raises():
    with pytest.raises(ValueError):
        parse_date_arg("32.13", TODAY)


def test_garbage_raises():
    with pytest.raises(ValueError):
        parse_date_arg("когда-нибудь", TODAY)
