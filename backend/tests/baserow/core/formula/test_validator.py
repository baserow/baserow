from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError

import pytest

from baserow.core.formula.validator import (
    ensure_date,
    ensure_datetime,
    ensure_duration,
    ensure_integer,
    ensure_string,
)


def test_ensure_date():
    assert ensure_date(None) is None
    assert ensure_date("2024-12-17") == date(2024, 12, 17)


@pytest.mark.parametrize("value", [1, 0.1, [], {}, False, "invalid"])
def test_ensure_date_throws_exception_for_invalid_value(value):
    with pytest.raises(ValidationError) as exc:
        ensure_date(value)
    assert exc.value.args[0] == "Value cannot be converted to a date."


def test_ensure_datetime():
    assert ensure_datetime(None) is None
    assert ensure_datetime("2024-12-17 12:00") == datetime(2024, 12, 17, 12, 0, 0)


def test_ensure_datetime_with_date_format():
    assert ensure_datetime(
        "05/05/2026 14:30", date_format="%d/%m/%Y %H:%M"
    ) == datetime(2026, 5, 5, 14, 30)
    assert ensure_datetime("2026-05-05", date_format="%Y-%m-%d") == datetime(2026, 5, 5)


def test_ensure_datetime_with_date_format_iso_takes_priority():
    assert ensure_datetime("2026-05-05T12:00:00", date_format="%d/%m/%Y") == datetime(
        2026, 5, 5, 12, 0, 0
    )


def test_ensure_datetime_strict_rejects_iso_when_format_differs():
    with pytest.raises(ValidationError):
        ensure_datetime("2026-05-06", date_format="%d/%m/%Y", strict=True)


def test_ensure_datetime_strict_accepts_matching_format():
    assert ensure_datetime(
        "06/05/2026", date_format="%d/%m/%Y", strict=True
    ) == datetime(2026, 5, 6)


def test_ensure_datetime_strict_none_value():
    assert ensure_datetime(None, date_format="%d/%m/%Y", strict=True) is None


def test_ensure_datetime_with_date_format_invalid_value():
    with pytest.raises(ValidationError) as exc:
        ensure_datetime("foo", date_format="%d/%m/%Y %H:%M")
    assert exc.value.args[0] == "Value cannot be converted to a datetime."


def test_ensure_datetime_with_date_format_none_value():
    assert ensure_datetime(None, date_format="%d/%m/%Y") is None


@pytest.mark.parametrize("value", [1, 0.1, [], {}, False, "invalid"])
def test_ensure_datetime_throws_exception_for_invalid_value(value):
    with pytest.raises(ValidationError) as exc:
        ensure_datetime(value)
    assert exc.value.args[0] == "Value cannot be converted to a datetime."


@pytest.mark.parametrize(
    "value,expected",
    [
        (timedelta(days=2), timedelta(days=2)),
        (timedelta(hours=3, minutes=30), timedelta(hours=3, minutes=30)),
        (timedelta(0), timedelta(0)),
        ("1 day", timedelta(days=1)),
        ("2 days", timedelta(days=2)),
        ("3 hours", timedelta(hours=3)),
        ("30 minutes", timedelta(minutes=30)),
        ("45 seconds", timedelta(seconds=45)),
        ("1 week", timedelta(weeks=1)),
        ("1 year", timedelta(days=365)),
        ("1 month", timedelta(days=30)),
        ("86400", timedelta(days=1)),
        ("3600", timedelta(hours=1)),
        ("60", timedelta(seconds=60)),
        ("0", timedelta(0)),
        ("1:30", timedelta(seconds=90)),
        ("0:01:30", timedelta(minutes=1, seconds=30)),
        ("1:30:00", timedelta(hours=1, minutes=30)),
        ("11:12:13.14", timedelta(hours=11, minutes=12, seconds=13.14)),
        ("1d", timedelta(days=1)),
        ("5h", timedelta(hours=5)),
        ("1d 12h", timedelta(days=1, hours=12)),
        ("1d 2h 3m", timedelta(days=1, hours=2, minutes=3)),
        ("1d 11:12:13", timedelta(days=1, hours=11, minutes=12, seconds=13)),
        ("12.5", timedelta(seconds=12.5)),
        ("0 days", timedelta(0)),
        ("0 hours", timedelta(0)),
        ("-1:30", timedelta(seconds=-90)),
        ("-1d 12h", timedelta(days=-1, hours=-12)),
        (60, timedelta(seconds=60)),
        (3600, timedelta(hours=1)),
        (86400, timedelta(days=1)),
        (0, timedelta(0)),
        (1.5, timedelta(seconds=1.5)),
    ],
)
def test_ensure_duration_passthrough(value, expected):
    assert ensure_duration(value) == expected


@pytest.mark.parametrize("value", ["foo", ""])
def test_ensure_duration_invalid_string(value):
    with pytest.raises(ValidationError) as e:
        ensure_duration(value)

    assert f"'{value}' is not a valid duration." in str(e)


@pytest.mark.parametrize("value", [None, [], {}])
def test_ensure_duration_invalid_type(value):
    with pytest.raises(ValidationError) as e:
        ensure_duration(value)

    assert e.value.args[0] == "Value cannot be converted to a duration."


@pytest.mark.parametrize(
    "value,expected",
    [
        (timedelta(0), "0"),
        (timedelta(days=1), "86400"),
        (timedelta(days=2), "172800"),
        (timedelta(hours=1), "3600"),
        (timedelta(days=1, hours=2, minutes=3, seconds=4), "93784"),
        (timedelta(seconds=90), "90"),
        (timedelta(seconds=-86400), "-86400"),
    ],
)
def test_ensure_string_with_timedelta(value, expected):
    assert ensure_string(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (timedelta(0), 0),
        (timedelta(days=1), 86400),
        (timedelta(hours=1), 3600),
        (timedelta(minutes=30), 1800),
        (timedelta(seconds=45), 45),
        (timedelta(days=2, hours=3), 183600),
    ],
)
def test_ensure_integer_with_timedelta(value, expected):
    assert ensure_integer(value) == expected
