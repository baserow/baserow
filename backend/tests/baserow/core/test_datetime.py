from datetime import date, datetime

import pytest

from baserow.core.datetime import FormattedDate, FormattedDateTime


@pytest.mark.parametrize(
    "value,date_format,expected",
    [
        (FormattedDate("2024-04-25"), "%d/%m/%Y", "25/04/2024"),
        (FormattedDateTime("2024-04-25 03:30"), "%m/%d/%Y", "04/25/2024"),
        (date(2024, 4, 25), "%d/%m/%Y", "25/04/2024"),
        (datetime(2024, 4, 25, 10, 30), "%d/%m/%Y", "25/04/2024"),
        ("2024-04-25", "%Y-%m-%d", "2024-04-25"),
        ("2025-08-06T14:54:14.000356Z", "%d/%m/%Y", "06/08/2025"),
    ],
)
def test_formatted_date(value, date_format, expected):
    if expected:
        formatted_date = FormattedDate(value, date_format)
        assert isinstance(formatted_date.date, date)
        assert formatted_date.date_format == date_format
        assert str(formatted_date) == expected
    else:
        with pytest.raises(ValueError):
            FormattedDate(value, date_format)


@pytest.mark.parametrize(
    "value,date_format,expected",
    [
        (FormattedDate("2024-04-25"), "%d/%m/%Y %H:%M", "25/04/2024 00:00"),
        (FormattedDateTime("2024-04-25 03:30"), "%m/%d/%Y %H:%M", "04/25/2024 03:30"),
        (date(2024, 4, 25), "%d/%m/%Y %H:%M", "25/04/2024 00:00"),
        (datetime(2024, 4, 25, 10, 30), "%d/%m/%Y %I:%M %p", "25/04/2024 10:30 AM"),
        ("2024-04-25 03:30", "%Y-%m-%d %H:%M", "2024-04-25 03:30"),
        ("2025-08-06T14:54:14.000356Z", "%Y-%m-%d %H:%M", "2025-08-06 14:54"),
    ],
)
def test_formatted_datetime(value, date_format, expected):
    if expected:
        formatted_datetime = FormattedDateTime(value, date_format)
        assert isinstance(formatted_datetime.datetime, datetime)
        assert formatted_datetime.date_format == date_format
        assert str(formatted_datetime) == expected
    else:
        with pytest.raises(ValueError):
            FormattedDateTime(value, date_format)
