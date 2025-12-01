from __future__ import annotations

import zoneinfo
from datetime import date, datetime
from functools import lru_cache


@lru_cache(maxsize=None)
def get_timezones():
    return zoneinfo.available_timezones()


class FormattedDate:
    """Wrapper around `datetime` object that also includes a format string."""

    def __init__(
        self,
        value: FormattedDate | FormattedDateTime | date | datetime | str,
        date_format: str = "%Y-%m-%d",
    ):
        if isinstance(value, FormattedDate):
            self.date = value.date
        elif isinstance(value, FormattedDateTime):
            self.date = value.datetime.date()
        elif isinstance(value, datetime):
            self.date = value.date()
        elif isinstance(value, date):
            self.date = value
        else:
            try:
                # Try ISO format first
                self.date = datetime.fromisoformat(value).date()
            except ValueError:
                # Fallback to specified format
                self.date = datetime.strptime(value, date_format).date()

        self.date_format = date_format

    def __str__(self) -> str:
        return self.date.strftime(self.date_format)


class FormattedDateTime:
    """Wrapper around `date` object that also includes a format string."""

    def __init__(
        self,
        value: FormattedDate | FormattedDateTime | date | datetime | str,
        date_format: str = "%Y-%m-%d %H:%M",
    ):
        if isinstance(value, FormattedDate):
            self.datetime = datetime.combine(value.date, datetime.min.time())
        elif isinstance(value, FormattedDateTime):
            self.datetime = value.datetime
        elif isinstance(value, datetime):
            self.datetime = value
        elif isinstance(value, date):
            self.datetime = datetime.combine(value, datetime.min.time())
        else:
            try:
                # Try ISO format first
                self.datetime = datetime.fromisoformat(value)
            except ValueError:
                # Fallback to specified format
                self.datetime = datetime.strptime(value, date_format)

        self.date_format = date_format

    def __str__(self) -> str:
        return self.datetime.strftime(self.date_format)
