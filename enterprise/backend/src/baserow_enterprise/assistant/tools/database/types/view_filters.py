from typing import Literal

from pydantic import Field

from baserow_enterprise.assistant.types import BaseModel

from .base import Date

# ---------------------------------------------------------------------------
# Filter config models (one per field type)
# ---------------------------------------------------------------------------


class TextFilterConfig(BaseModel):
    type: Literal["text"] = Field(..., description="Must be 'text'.")
    operator: Literal[
        "equal", "not_equal", "contains", "contains_not", "empty", "not_empty"
    ] = Field(..., description="Filter operator.")
    value: str = Field(
        ...,
        description="The text value to filter on. Use '' for empty/not_empty operators.",
    )

    def get_django_orm_type(self, field, **kwargs) -> str:
        return self.operator

    def get_django_orm_value(self, field, **kwargs) -> str:
        return self.value


class NumberFilterConfig(BaseModel):
    type: Literal["number"] = Field(..., description="Must be 'number'.")
    operator: Literal[
        "equal", "not_equal", "higher_than", "lower_than", "empty", "not_empty"
    ] = Field(..., description="Filter operator.")
    value: float = Field(
        ...,
        description="The number value to filter on. Use 0 for empty/not_empty operators.",
    )
    or_equal: bool = Field(
        ...,
        description=(
            "For higher_than/lower_than: include equal values. false otherwise."
        ),
    )

    _OR_EQUAL_MAP = {
        "higher_than": "higher_than_or_equal",
        "lower_than": "lower_than_or_equal",
    }

    def get_django_orm_type(self, field, **kwargs) -> str:
        if self.or_equal and self.operator in self._OR_EQUAL_MAP:
            return self._OR_EQUAL_MAP[self.operator]
        return self.operator

    def get_django_orm_value(self, field, **kwargs) -> str:
        return str(self.value)


class DateFilterConfig(BaseModel):
    type: Literal["date"] = Field(..., description="Must be 'date'.")
    operator: Literal["equal", "not_equal", "after", "before"] = Field(
        ..., description="Filter operator."
    )
    value: Date | int | None = Field(
        ...,
        description=(
            "Date object for exact_date mode, integer for relative modes "
            "(nr_days_ago, etc.), None otherwise."
        ),
    )
    mode: Literal[
        "today",
        "yesterday",
        "tomorrow",
        "this_week",
        "last_week",
        "next_week",
        "this_month",
        "last_month",
        "next_month",
        "this_year",
        "last_year",
        "next_year",
        "nr_days_ago",
        "nr_days_from_now",
        "nr_weeks_ago",
        "nr_weeks_from_now",
        "nr_months_ago",
        "nr_months_from_now",
        "nr_years_ago",
        "nr_years_from_now",
        "exact_date",
    ] = Field(
        ...,
        description=(
            "The date filter mode. Use 'exact_date' for an exact date, "
            "relative modes like 'today'/'nr_days_ago' otherwise."
        ),
    )
    or_equal: bool = Field(
        ...,
        description="For after/before: include equal values. false otherwise.",
    )

    _ORM_TYPE_MAP = {
        "equal": "date_is",
        "not_equal": "date_is_not",
        "after": "date_is_after",
        "before": "date_is_before",
    }
    _OR_EQUAL_MAP = {
        "after": "date_is_on_or_after",
        "before": "date_is_on_or_before",
    }

    def get_django_orm_type(self, field, **kwargs) -> str:
        if self.or_equal and self.operator in self._OR_EQUAL_MAP:
            return self._OR_EQUAL_MAP[self.operator]
        return self._ORM_TYPE_MAP[self.operator]

    def get_django_orm_value(self, field, **kwargs) -> str:
        timezone = kwargs.get("timezone", "UTC")
        if isinstance(self.value, Date):
            value = self.value.to_django_orm()
        elif isinstance(self.value, int):
            value = str(self.value)
        else:
            value = ""
        return f"{timezone}?{value}?{self.mode}"


class SingleSelectFilterConfig(BaseModel):
    type: Literal["single_select"] = Field(..., description="Must be 'single_select'.")
    operator: Literal["is_any_of", "is_none_of"] = Field(
        ..., description="Filter operator."
    )
    value: list[str] = Field(..., description="The select option names to filter on.")

    _ORM_TYPE_MAP = {
        "is_any_of": "single_select_is_any_of",
        "is_none_of": "single_select_is_none_of",
    }

    def get_django_orm_type(self, field, **kwargs) -> str:
        return self._ORM_TYPE_MAP[self.operator]

    def get_django_orm_value(self, field, **kwargs) -> str:
        values = set(v.lower() for v in self.value)
        valid_option_ids = [
            option.id
            for option in field.select_options.all()
            if option.value.lower() in values
        ]
        return ",".join(str(v) for v in valid_option_ids)


class MultipleSelectFilterConfig(BaseModel):
    type: Literal["multiple_select"] = Field(
        ..., description="Must be 'multiple_select'."
    )
    operator: Literal["is_any_of", "is_none_of"] = Field(
        ..., description="Filter operator."
    )
    value: list[str] = Field(..., description="The select option names to filter on.")

    _ORM_TYPE_MAP = {
        "is_any_of": "multiple_select_has",
        "is_none_of": "multiple_select_has_not",
    }

    def get_django_orm_type(self, field, **kwargs) -> str:
        return self._ORM_TYPE_MAP[self.operator]

    def get_django_orm_value(self, field, **kwargs) -> str:
        values = set(v.lower() for v in self.value)
        valid_option_ids = [
            option.id
            for option in field.select_options.all()
            if option.value.lower() in values
        ]
        return ",".join(str(v) for v in valid_option_ids)


class LinkRowFilterConfig(BaseModel):
    type: Literal["link_row"] = Field(..., description="Must be 'link_row'.")
    operator: Literal["has", "has_not"] = Field(..., description="Filter operator.")
    value: int = Field(..., description="The linked record ID to filter on.")

    _ORM_TYPE_MAP = {
        "has": "link_row_has",
        "has_not": "link_row_has_not",
    }

    def get_django_orm_type(self, field, **kwargs) -> str:
        return self._ORM_TYPE_MAP[self.operator]

    def get_django_orm_value(self, field, **kwargs) -> str:
        return str(self.value)


class BooleanFilterConfig(BaseModel):
    type: Literal["boolean"] = Field(..., description="Must be 'boolean'.")
    operator: Literal["is"] = Field(..., description="Must be 'is'.")
    value: bool = Field(..., description="The boolean value to filter on.")

    def get_django_orm_type(self, field, **kwargs) -> str:
        return "boolean"

    def get_django_orm_value(self, field, **kwargs) -> str:
        return "1" if self.value else "0"


# ---------------------------------------------------------------------------
# Config union and wrapper types
# ---------------------------------------------------------------------------

# Plain union (no discriminator) — produces anyOf in JSON schema for Groq compat
AnyFilterConfig = (
    TextFilterConfig
    | NumberFilterConfig
    | DateFilterConfig
    | SingleSelectFilterConfig
    | MultipleSelectFilterConfig
    | LinkRowFilterConfig
    | BooleanFilterConfig
)


class ViewFilterItemCreate(BaseModel):
    """Model for creating a new view filter: field_id + config."""

    field_id: int = Field(..., description="The ID of the field to filter on.")
    config: AnyFilterConfig = Field(
        ..., description="Type-specific filter configuration."
    )


class ViewFilterItem(ViewFilterItemCreate):
    """Model for an existing view filter (with ID)."""

    id: int = Field(..., description="The unique identifier of the view filter.")


AnyViewFilterItemCreate = ViewFilterItemCreate
AnyViewFilterItem = ViewFilterItem


class ViewFiltersArgs(BaseModel):
    view_id: int
    filters: list[AnyViewFilterItemCreate]
