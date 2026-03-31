from typing import Literal

from pydantic import Field, model_validator

from baserow_enterprise.assistant.types import BaseModel

from .base import parse_date

# ---------------------------------------------------------------------------
# Flat filter model
# ---------------------------------------------------------------------------

FilterType = Literal[
    "text", "number", "date", "single_select", "multiple_select", "link_row", "boolean"
]

_OPERATORS: dict[str, tuple[str, ...]] = {
    "text": ("equal", "not_equal", "contains", "contains_not", "empty", "not_empty"),
    "number": ("equal", "not_equal", "higher_than", "lower_than", "empty", "not_empty"),
    "date": ("equal", "not_equal", "after", "before"),
    "single_select": ("is_any_of", "is_none_of"),
    "multiple_select": ("is_any_of", "is_none_of"),
    "link_row": ("has", "has_not"),
    "boolean": ("equal",),
}

# Operator aliases: normalize LLM-natural names to Baserow names before validation.
_OPERATOR_ALIASES: dict[str, str] = {
    "equals": "equal",
    "is": "equal",
    "not_equals": "not_equal",
    "is_not": "not_equal",
    "greater_than": "higher_than",
    "greater_than_or_equal": "higher_than",  # or_equal flag handles the rest
    "less_than": "lower_than",
    "less_than_or_equal": "lower_than",  # or_equal flag handles the rest
    "gte": "higher_than",
    "lte": "lower_than",
    "gt": "higher_than",
    "lt": "lower_than",
    "neq": "not_equal",
    "ne": "not_equal",
    "eq": "equal",
}

DateFilterMode = Literal[
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
]


# ---------------------------------------------------------------------------
# ORM type dispatch: (filter, field, **kwargs) -> str
# ---------------------------------------------------------------------------

_NUMBER_OR_EQUAL = {
    "higher_than": "higher_than_or_equal",
    "lower_than": "lower_than_or_equal",
}

_DATE_ORM_TYPE = {
    "equal": "date_is",
    "not_equal": "date_is_not",
    "after": "date_is_after",
    "before": "date_is_before",
}

_DATE_OR_EQUAL = {
    "after": "date_is_on_or_after",
    "before": "date_is_on_or_before",
}

_SINGLE_SELECT_ORM_TYPE = {
    "is_any_of": "single_select_is_any_of",
    "is_none_of": "single_select_is_none_of",
}

_MULTIPLE_SELECT_ORM_TYPE = {
    "is_any_of": "multiple_select_has",
    "is_none_of": "multiple_select_has_not",
}

_LINK_ROW_ORM_TYPE = {
    "has": "link_row_has",
    "has_not": "link_row_has_not",
}

_GET_ORM_TYPE = {
    "text": lambda f, field, **kw: f.operator,
    "number": lambda f, field, **kw: (
        _NUMBER_OR_EQUAL.get(f.operator, f.operator) if f.or_equal else f.operator
    ),
    "date": lambda f, field, **kw: (
        _DATE_OR_EQUAL[f.operator]
        if f.or_equal and f.operator in _DATE_OR_EQUAL
        else _DATE_ORM_TYPE[f.operator]
    ),
    "single_select": lambda f, field, **kw: _SINGLE_SELECT_ORM_TYPE[f.operator],
    "multiple_select": lambda f, field, **kw: _MULTIPLE_SELECT_ORM_TYPE[f.operator],
    "link_row": lambda f, field, **kw: _LINK_ROW_ORM_TYPE[f.operator],
    "boolean": lambda f, field, **kw: "equal",
}


# ---------------------------------------------------------------------------
# ORM value dispatch: (filter, field, **kwargs) -> str
# ---------------------------------------------------------------------------


def _select_orm_value(f, field, **kwargs):
    values = set(v.lower() for v in f.value)
    valid_option_ids = [
        option.id
        for option in field.select_options.all()
        if option.value.lower() in values
    ]
    return ",".join(str(v) for v in valid_option_ids)


def _date_orm_value(f, field, **kwargs):
    timezone = kwargs.get("timezone", "UTC")
    if isinstance(f.value, str):
        value = parse_date(f.value).isoformat()
    elif isinstance(f.value, int):
        value = str(f.value)
    else:
        value = ""
    return f"{timezone}?{value}?{f.mode}"


_GET_ORM_VALUE = {
    "text": lambda f, field, **kw: f.value
    if isinstance(f.value, str)
    else str(f.value or ""),
    "number": lambda f, field, **kw: str(f.value),
    "date": _date_orm_value,
    "single_select": _select_orm_value,
    "multiple_select": _select_orm_value,
    "link_row": lambda f, field, **kw: str(f.value),
    "boolean": lambda f, field, **kw: "1" if f.value else "0",
}


# ---------------------------------------------------------------------------
# ViewFilterItemCreate
# ---------------------------------------------------------------------------


class ViewFilterItemCreate(BaseModel):
    """Flat model for creating a view filter: field_id + type + operator + value."""

    field_id: int = Field(..., description="Field ID to filter on.")
    type: FilterType = Field(..., description="Must match field type.")
    operator: str = Field(
        ...,
        description=(
            "Filter operator. "
            "text: equal/not_equal/contains/contains_not/empty/not_empty. "
            "number: equal/not_equal/greater_than/less_than/empty/not_empty "
            "(use or_equal=true for ≥/≤). "
            "date: equal/not_equal/after/before (use or_equal=true for on_or_after/on_or_before). "
            "single_select/multiple_select: is_any_of/is_none_of. "
            "link_row: has/has_not. "
            "boolean: equal."
        ),
    )
    value: str | float | int | bool | list[str] | None = Field(
        None,
        description="Filter value (type-dependent).",
    )
    mode: DateFilterMode | None = Field(None, description="(date) Date filter mode.")
    or_equal: bool = Field(False, description="(number, date) Include equal values.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_operator(cls, data):
        if isinstance(data, dict) and "operator" in data:
            op = data["operator"]
            normalized = _OPERATOR_ALIASES.get(op)
            if normalized:
                data = dict(data)
                data["operator"] = normalized
                # Auto-set or_equal for _or_equal variants
                if "or_equal" in op:
                    data.setdefault("or_equal", True)
        return data

    @model_validator(mode="after")
    def _validate_per_type(self):
        valid = _OPERATORS.get(self.type)
        if valid and self.operator not in valid:
            raise ValueError(
                f"Invalid operator '{self.operator}' for type '{self.type}'. "
                f"Valid operators: {', '.join(valid)}"
            )
        if self.type == "date" and self.mode is None:
            raise ValueError("date filter requires 'mode'.")
        return self

    def get_django_orm_type(self, field, **kwargs) -> str:
        return _GET_ORM_TYPE[self.type](self, field, **kwargs)

    def get_django_orm_value(self, field, **kwargs) -> str:
        return _GET_ORM_VALUE[self.type](self, field, **kwargs)


class ViewFilterItem(ViewFilterItemCreate):
    """Existing view filter with ID."""

    id: int = Field(..., description="The unique identifier of the view filter.")


AnyViewFilterItemCreate = ViewFilterItemCreate
AnyViewFilterItem = ViewFilterItem


class ViewFiltersArgs(BaseModel):
    view_id: int
    filters: list[ViewFilterItemCreate]
