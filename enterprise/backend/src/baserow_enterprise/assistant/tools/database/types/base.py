from datetime import date, datetime

from pydantic import Field

from baserow_enterprise.assistant.types import BaseModel


# Somehow LLMs struggle with dates
class Date(BaseModel):
    year: int = Field(..., description="year (i.e. 2025).")
    month: int = Field(..., description="month (1-12).")
    day: int = Field(..., description="day (1-31).")

    def to_django_orm(self):
        return date(self.year, self.month, self.day).isoformat()

    @classmethod
    def from_django_orm(cls, orm_date: date) -> "Date":
        d = orm_date
        return cls(year=d.year, month=d.month, day=d.day)


class Datetime(Date):
    hour: int = Field(..., description="hour (0-23).")
    minute: int = Field(..., description="minute (0-59).")

    def to_django_orm(self):
        return datetime(
            self.year, self.month, self.day, self.hour, self.minute
        ).isoformat()

    @classmethod
    def from_django_orm(cls, orm_datetime: datetime) -> "Datetime":
        dt = orm_datetime
        return cls(
            year=dt.year, month=dt.month, day=dt.day, hour=dt.hour, minute=dt.minute
        )
