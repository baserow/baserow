from datetime import date, datetime

from pydantic import model_validator

from baserow_enterprise.assistant.types import BaseModel


class Date(BaseModel):
    year: int
    month: int
    day: int

    @model_validator(mode="after")
    def _validate_date(self):
        # Eagerly check that the combination is a real calendar date so
        # invalid values (e.g. September 31) are caught during Pydantic
        # validation — triggering pydantic-ai's retry — instead of
        # crashing inside to_django_orm().
        date(self.year, self.month, self.day)
        return self

    def to_django_orm(self):
        return date(self.year, self.month, self.day).isoformat()

    @classmethod
    def from_django_orm(cls, orm_date: date) -> "Date":
        d = orm_date
        return cls(year=d.year, month=d.month, day=d.day)


class Datetime(Date):
    hour: int
    minute: int

    @model_validator(mode="after")
    def _validate_datetime(self):
        datetime(self.year, self.month, self.day, self.hour, self.minute)
        return self

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
