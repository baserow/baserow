from datetime import date, datetime, timedelta

from django.core.exceptions import ValidationError

import pytest

from baserow.core.formula.validator import (
    ensure_date,
    ensure_date_interval,
    ensure_datetime,
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


@pytest.mark.parametrize("value", [1, 0.1, [], {}, False, "invalid"])
def test_ensure_datetime_throws_exception_for_invalid_value(value):
    with pytest.raises(ValidationError) as exc:
        ensure_datetime(value)
    assert exc.value.args[0] == "Value cannot be converted to a datetime."


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
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
        (60, timedelta(seconds=60)),
        (3600, timedelta(hours=1)),
        (86400, timedelta(days=1)),
        (0, timedelta(0)),
        (1.5, timedelta(seconds=1.5)),
    ],
)
def test_ensure_date_interval_passthrough(value, expected):
    assert ensure_date_interval(value) == expected


@pytest.mark.parametrize("value", ["foo", ""])
def test_ensure_date_interval_invalid_string(value):
    with pytest.raises(ValidationError) as e:
        ensure_date_interval(value)

    assert f"'{value}' is not a valid interval string." in str(e)


@pytest.mark.parametrize("value", [[], {}])
def test_ensure_date_interval_invalid_type(value):
    with pytest.raises(ValidationError) as e:
        ensure_date_interval(value)

    assert e.value.args[0] == "Value cannot be converted to a date interval."


@pytest.mark.parametrize(
    "value,expected",
    [
        (timedelta(0), "0 seconds"),
        (timedelta(days=1), "1 day"),
        (timedelta(days=2), "2 days"),
        (timedelta(hours=1), "1 hour"),
        (timedelta(hours=3, minutes=30), "3 hours 30 minutes"),
        (
            timedelta(days=1, hours=2, minutes=3, seconds=4),
            "1 day 2 hours 3 minutes 4 seconds",
        ),
        (timedelta(seconds=90), "1 minute 30 seconds"),
        (timedelta(seconds=-86400), "-1 day"),
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
