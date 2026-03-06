from datetime import date, datetime

from dateutil import parser as _dateutil_parser


def _normalize(value: str) -> str:
    """Replace common separator variants so fromisoformat can parse them."""

    return value.replace("/", "-").strip()


def parse_date(value: str) -> date:
    """
    Parse a date string into a date object.

    Tries ISO 8601 first, then falls back to dateutil for fuzzy formats
    like ``Jan 5, 2023`` or ``05/01/2023``.
    """

    try:
        return date.fromisoformat(_normalize(value))
    except ValueError:
        return _dateutil_parser.parse(value).date()


def parse_datetime(value: str) -> datetime:
    """
    Parse a datetime string into a datetime object.

    Tries ISO 8601 first, then falls back to dateutil for fuzzy formats
    like ``Jan 5, 2023 10:00 AM``.
    """

    try:
        return datetime.fromisoformat(_normalize(value))
    except ValueError:
        return _dateutil_parser.parse(value)


def format_date(value: date) -> str:
    """Format a date as ISO 8601 (``YYYY-MM-DD``)."""

    return value.isoformat()


def format_datetime(value: datetime) -> str:
    """Format a datetime as ISO 8601 (``YYYY-MM-DDTHH:MM``), without seconds."""

    return value.strftime("%Y-%m-%dT%H:%M")
