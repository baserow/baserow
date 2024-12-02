from __future__ import annotations

from datetime import date, datetime


class FormattedDate:
    """Wrapper around `datetime` object that also includes a format string."""

    def __init__(
        self,
        value: FormattedDate | FormattedDateTime | date | datetime | str,
        format: str = "%Y-%m-%d",
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
            self.date = datetime.strptime(value, format).date()

        self.format = format

    def __str__(self) -> str:
        return self.date.strftime(self.format)


class FormattedDateTime:
    """Wrapper around `date` object that also includes a format string."""

    def __init__(
        self,
        value: FormattedDate | FormattedDateTime | date | datetime | str,
        format: str = "%Y-%m-%d %H:%M",
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
            self.datetime = datetime.strptime(value, format)

        self.format = format

    def __str__(self) -> str:
        return self.datetime.strftime(self.format)
