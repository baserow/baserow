from typing import Literal

from pydantic import Field

from baserow_enterprise.assistant.types import Annotated, BaseModel

from .base import Date


class ViewFilterItemCreate(BaseModel):
    """Model for creating a new view filter (no ID)."""

    field_id: int = Field(...)
    type: str = Field(...)
    operator: str = Field(...)
    value: str = Field(...)

    def get_django_orm_type(self, field, **kwargs) -> str:
        return self.operator

    def get_django_orm_value(self, field, **kwargs) -> str:
        return self.value


class ViewFilterItem(ViewFilterItemCreate):
    """Model for an existing view filter (with ID)."""

    id: int = Field(..., description="The unique identifier of the view filter.")


class TextViewFilterItemCreate(ViewFilterItemCreate):
    type: Literal["text"] = Field(..., description="A text filter.")
    value: str = Field(..., description="The text value to filter on.")


class TextEqualViewFilterItemCreate(TextViewFilterItemCreate):
    operator: Literal["equal"] = Field(
        ..., description="Checks if the field is equal to the value."
    )


class TextEqualViewFilterItem(TextEqualViewFilterItemCreate, ViewFilterItem):
    pass


class TextNotEqualViewFilterItemCreate(TextViewFilterItemCreate):
    operator: Literal["not_equal"] = Field(
        ..., description="Checks if the field is not equal to the value."
    )


class TextNotEqualViewFilterItem(TextNotEqualViewFilterItemCreate, ViewFilterItem):
    pass


class TextContainsViewFilterItemCreate(TextViewFilterItemCreate):
    operator: Literal["contains"] = Field(
        ..., description="Checks if the field contains the value."
    )


class TextContainsViewFilterItem(TextContainsViewFilterItemCreate, ViewFilterItem):
    pass


class TextNotContainsViewFilterItemCreate(TextViewFilterItemCreate):
    operator: Literal["contains_not"] = Field(
        ..., description="Checks if the field does not contain the value."
    )


class TextNotContainsViewFilterItem(
    TextNotContainsViewFilterItemCreate, ViewFilterItem
):
    pass


class TextEmptyViewFilterItemCreate(TextViewFilterItemCreate):
    operator: Literal["empty"] = Field(..., description="Checks if the field is empty.")


class TextEmptyViewFilterItem(TextEmptyViewFilterItemCreate, ViewFilterItem):
    pass


class TextNotEmptyViewFilterItemCreate(TextViewFilterItemCreate):
    operator: Literal["not_empty"] = Field(
        ..., description="Checks if the field is not empty."
    )


class TextNotEmptyViewFilterItem(TextNotEmptyViewFilterItemCreate, ViewFilterItem):
    pass


AnyTextViewFilterItemCreate = Annotated[
    TextEqualViewFilterItemCreate
    | TextNotEqualViewFilterItemCreate
    | TextContainsViewFilterItemCreate
    | TextNotContainsViewFilterItemCreate
    | TextEmptyViewFilterItemCreate
    | TextNotEmptyViewFilterItemCreate,
    Field(discriminator="operator"),
]

AnyTextViewFilterItem = Annotated[
    TextEqualViewFilterItem
    | TextNotEqualViewFilterItem
    | TextContainsViewFilterItem
    | TextNotContainsViewFilterItem
    | TextEmptyViewFilterItem
    | TextNotEmptyViewFilterItem,
    Field(discriminator="operator"),
]


class NumberViewFilterItemCreate(ViewFilterItemCreate):
    type: Literal["number"] = Field(..., description="A number filter.")
    value: float = Field(..., description="The number value to filter on.")

    def get_django_orm_value(self, field, **kwargs) -> str:
        return str(self.value)


class NumberViewFilterItem(NumberViewFilterItemCreate, ViewFilterItem):
    pass


class NumberEqualsViewFilterItemCreate(NumberViewFilterItemCreate):
    operator: Literal["equal"] = Field(
        ..., description="Checks if the field is equal to the value."
    )


class NumberEqualsViewFilterItem(NumberEqualsViewFilterItemCreate, ViewFilterItem):
    pass


class NumberNotEqualsViewFilterItemCreate(NumberViewFilterItemCreate):
    operator: Literal["not_equal"] = Field(
        ..., description="Checks if the field is not equal to the value."
    )


class NumberNotEqualsViewFilterItem(
    NumberNotEqualsViewFilterItemCreate, ViewFilterItem
):
    pass


class NumberHigherThanViewFilterItemCreate(NumberViewFilterItemCreate):
    operator: Literal["higher_than"] = Field(
        ..., description="Checks if the field is higher than the value."
    )
    or_equal: bool = Field(
        False,
        description="If true, checks if the field is higher than or equal to the value.",
    )


class NumberHigherThanViewFilterItem(
    NumberHigherThanViewFilterItemCreate, ViewFilterItem
):
    pass


class NumberLowerThanViewFilterItemCreate(NumberViewFilterItemCreate):
    operator: Literal["lower_than"] = Field(
        ..., description="Checks if the field is lower than the value."
    )
    or_equal: bool = Field(
        False,
        description="If true, checks if the field is lower than or equal to the value.",
    )


class NumberLowerThanViewFilterItem(
    NumberLowerThanViewFilterItemCreate, ViewFilterItem
):
    pass


class NumberEmptyViewFilterItemCreate(NumberViewFilterItemCreate):
    operator: Literal["empty"] = Field(..., description="Checks if the field is empty.")


class NumberEmptyViewFilterItem(NumberEmptyViewFilterItemCreate, ViewFilterItem):
    pass


class NumberNotEmptyViewFilterItemCreate(NumberViewFilterItemCreate):
    operator: Literal["not_empty"] = Field(
        ..., description="Checks if the field is not empty."
    )


class NumberNotEmptyViewFilterItem(NumberNotEmptyViewFilterItemCreate, ViewFilterItem):
    pass


AnyNumberViewFilterItemCreate = Annotated[
    NumberEqualsViewFilterItemCreate
    | NumberNotEqualsViewFilterItemCreate
    | NumberHigherThanViewFilterItemCreate
    | NumberLowerThanViewFilterItemCreate
    | NumberEmptyViewFilterItemCreate
    | NumberNotEmptyViewFilterItemCreate,
    Field(discriminator="operator"),
]

AnyNumberViewFilterItem = Annotated[
    NumberEqualsViewFilterItem
    | NumberNotEqualsViewFilterItem
    | NumberHigherThanViewFilterItem
    | NumberLowerThanViewFilterItem
    | NumberEmptyViewFilterItem
    | NumberNotEmptyViewFilterItem,
    Field(discriminator="operator"),
]


class DateViewFilterItemCreate(ViewFilterItemCreate):
    type: Literal["date"] = Field(..., description="A date filter.")
    value: Date | int | None = Field(
        ...,
        description="\n".join(
            [
                "The date value to filter on.",
                "Use an integer for days/weeks/months/years ago/from now.",
                "Use a date object for an exact date.",
                "None otherwise.",
            ]
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
        "exact_date",
        description="The mode to use for the date filter. ALWAYS use the right mode if available. Use 'exact_date' if you have an exact date.",
    )

    def get_django_orm_value(self, field, **kwargs) -> str:
        timezone = kwargs.get("timezone", "UTC")

        if isinstance(self.value, Date):
            value = self.value.to_django_orm()
        elif isinstance(self.value, int):
            value = str(self.value)
        else:
            value = ""

        return f"{timezone}?{value}?{self.mode}"


class DateEqualsViewFilterItemCreate(DateViewFilterItemCreate):
    operator: Literal["equal"] = Field(
        ..., description="Checks if the field is equal to the value."
    )

    def get_django_orm_type(self, field, **kwargs) -> str:
        return "date_is"


class DateEqualsViewFilterItem(DateEqualsViewFilterItemCreate, ViewFilterItem):
    pass


class DateNotEqualsViewFilterItemCreate(DateViewFilterItemCreate):
    operator: Literal["not_equal"] = Field(
        ..., description="Checks if the field is not equal to the value."
    )

    def get_django_orm_type(self, field, **kwargs) -> str:
        return "date_is_not"


class DateNotEqualsViewFilterItem(DateNotEqualsViewFilterItemCreate, ViewFilterItem):
    pass


class DateAfterViewFilterItemCreate(DateViewFilterItemCreate):
    operator: Literal["after"] = Field(
        ..., description="Checks if the field is after the value."
    )
    or_equal: bool = Field(
        False,
        description="If true, checks if the field is after or equal to the value.",
    )

    def get_django_orm_type(self, field, **kwargs) -> str:
        return "date_is_on_or_after" if self.or_equal else "date_is_after"


class DateAfterViewFilterItem(DateAfterViewFilterItemCreate, ViewFilterItem):
    pass


class DateBeforeViewFilterItemCreate(DateViewFilterItemCreate):
    operator: Literal["before"] = Field(
        ..., description="Checks if the field is before the value."
    )
    or_equal: bool = Field(
        False,
        description="If true, checks if the field is before or equal to the value.",
    )

    def get_django_orm_type(self, field, **kwargs) -> str:
        return "date_is_on_or_before" if self.or_equal else "date_is_before"


class DateBeforeViewFilterItem(DateBeforeViewFilterItemCreate, ViewFilterItem):
    pass


AnyDateViewFilterItemCreate = Annotated[
    DateEqualsViewFilterItemCreate
    | DateNotEqualsViewFilterItemCreate
    | DateAfterViewFilterItemCreate
    | DateBeforeViewFilterItemCreate,
    Field(discriminator="operator"),
]
AnyDateViewFilterItem = Annotated[
    DateEqualsViewFilterItem
    | DateNotEqualsViewFilterItem
    | DateAfterViewFilterItem
    | DateBeforeViewFilterItem,
    Field(discriminator="operator"),
]


class SingleSelectViewFilterItemCreate(ViewFilterItemCreate):
    type: Literal["single_select"] = Field(..., description="A single select filter.")
    value: list[str] = Field(
        ..., description="The select option value(s) to filter on."
    )

    def get_django_orm_value(self, field, **kwargs) -> str:
        values = set(v.lower() for v in self.value)
        valid_option_ids = [
            option.id
            for option in field.select_options.all()
            if option.value.lower() in values
        ]
        return ",".join([str(v) for v in valid_option_ids])


class SingleSelectIsAnyViewFilterItemCreate(SingleSelectViewFilterItemCreate):
    operator: Literal["is_any_of"] = Field(
        ..., description="Checks if the field is equal to any of the values "
    )

    def get_django_orm_type(self, field, **kwargs):
        return "single_select_is_any_of"


class SingleSelectIsAnyViewFilterItem(
    SingleSelectIsAnyViewFilterItemCreate, ViewFilterItem
):
    pass


class SingleSelectIsNoneOfNotViewFilterItemCreate(SingleSelectViewFilterItemCreate):
    operator: Literal["is_none_of"] = Field(
        ..., description="Checks if the field is not equal to the value."
    )

    def get_django_orm_type(self, field, **kwargs):
        return "single_select_is_none_of"


class SingleSelectIsNoneOfNotViewFilterItem(
    SingleSelectIsNoneOfNotViewFilterItemCreate, ViewFilterItem
):
    pass


AnySingleSelectViewFilterItemCreate = Annotated[
    SingleSelectIsAnyViewFilterItemCreate | SingleSelectIsNoneOfNotViewFilterItemCreate,
    Field(discriminator="operator"),
]

AnySingleSelectViewFilterItem = Annotated[
    SingleSelectIsAnyViewFilterItem | SingleSelectIsNoneOfNotViewFilterItem,
    Field(discriminator="operator"),
]


class MultipleSelectViewFilterItemCreate(ViewFilterItemCreate):
    type: Literal["multiple_select"] = Field(
        ..., description="A multiple select filter."
    )
    value: list[str] = Field(
        ..., description="The select option value(s) to filter on."
    )

    def get_django_orm_value(self, field, **kwargs) -> str:
        values = set(v.lower() for v in self.value)
        valid_option_ids = [
            option.id
            for option in field.select_options.all()
            if option.value.lower() in values
        ]
        return ",".join([str(v) for v in valid_option_ids])


class MultipleSelectIsAnyViewFilterItemCreate(MultipleSelectViewFilterItemCreate):
    operator: Literal["is_any_of"] = Field(
        ..., description="Checks if the field is equal to any of the values "
    )

    def get_django_orm_type(self, field, **kwargs):
        return "multiple_select_has"


class MultipleSelectIsAnyViewFilterItem(
    MultipleSelectIsAnyViewFilterItemCreate, ViewFilterItem
):
    pass


class MultipleSelectIsNoneOfNotViewFilterItemCreate(MultipleSelectViewFilterItemCreate):
    operator: Literal["is_none_of"] = Field(
        ..., description="Checks if the field is not equal to the value."
    )

    def get_django_orm_type(self, field, **kwargs):
        return "multiple_select_has_not"


class MultipleSelectIsNoneOfNotViewFilterItem(
    MultipleSelectIsNoneOfNotViewFilterItemCreate, ViewFilterItem
):
    pass


AnyMultipleSelectViewFilterItemCreate = Annotated[
    MultipleSelectIsAnyViewFilterItemCreate
    | MultipleSelectIsNoneOfNotViewFilterItemCreate,
    Field(discriminator="operator"),
]

AnyMultipleSelectViewFilterItem = Annotated[
    MultipleSelectIsAnyViewFilterItem | MultipleSelectIsNoneOfNotViewFilterItem,
    Field(discriminator="operator"),
]


class LinkRowViewFilterItemCreate(ViewFilterItemCreate):
    type: Literal["link_row"] = Field(..., description="A link row filter.")
    value: int = Field(..., description="The linked record ID to filter on.")

    def get_django_orm_value(self, field, **kwargs) -> str:
        return str(self.value)


class LinkRowHasViewFilterItemCreate(LinkRowViewFilterItemCreate):
    operator: Literal["has"] = Field(
        ..., description="Checks if the field has the linked record."
    )

    def get_django_orm_type(self, field, **kwargs):
        return "link_row_has"


class LinkRowHasViewFilterItem(LinkRowHasViewFilterItemCreate, ViewFilterItem):
    pass


class LinkRowHasNotViewFilterItemCreate(LinkRowViewFilterItemCreate):
    operator: Literal["has_not"] = Field(
        ..., description="Checks if the field does not have the linked record."
    )

    def get_django_orm_type(self, field, **kwargs):
        return "link_row_has_not"


class LinkRowHasNotViewFilterItem(LinkRowHasNotViewFilterItemCreate, ViewFilterItem):
    pass


AnyLinkRowViewFilterItemCreate = Annotated[
    LinkRowHasViewFilterItemCreate | LinkRowHasNotViewFilterItemCreate,
    Field(discriminator="operator"),
]

AnyLinkRowViewFilterItem = Annotated[
    LinkRowHasViewFilterItem | LinkRowHasNotViewFilterItem,
    Field(discriminator="operator"),
]


class BooleanViewFilterItemCreate(ViewFilterItemCreate):
    type: Literal["boolean"] = Field(..., description="A boolean filter.")
    value: bool = Field(..., description="The boolean value to filter on.")

    def get_django_orm_value(self, field, **kwargs) -> str:
        return "1" if self.value else "0"


class BooleanIsViewFilterItemCreate(BooleanViewFilterItemCreate):
    operator: Literal["is"] = Field(..., description="Checks if the field is true.")
    value: bool = Field(..., description="The boolean value to filter on.")

    def get_django_orm_type(self, field, **kwargs) -> str:
        return "boolean"


class BooleanIsTrueViewFilterItem(BooleanIsViewFilterItemCreate, ViewFilterItem):
    pass


AnyViewFilterItemCreate = Annotated[
    AnyTextViewFilterItemCreate
    | AnyNumberViewFilterItemCreate
    | AnyDateViewFilterItemCreate
    | AnySingleSelectViewFilterItemCreate
    | AnyLinkRowViewFilterItemCreate
    | BooleanViewFilterItemCreate
    | MultipleSelectViewFilterItemCreate,
    Field(discriminator="type"),
]

AnyViewFilterItem = Annotated[
    AnyTextViewFilterItem
    | AnyNumberViewFilterItem
    | AnyDateViewFilterItem
    | AnySingleSelectViewFilterItem
    | AnyLinkRowViewFilterItem
    | BooleanIsTrueViewFilterItem
    | MultipleSelectIsAnyViewFilterItem,
    Field(discriminator="type"),
]


class ViewFiltersArgs(BaseModel):
    view_id: int
    filters: list[AnyViewFilterItemCreate]
