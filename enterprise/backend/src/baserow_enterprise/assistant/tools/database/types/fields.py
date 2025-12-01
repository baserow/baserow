from typing import Annotated, Literal, Type

from django.db.models import Q

from baserow_premium.permission_manager import Table
from pydantic import Field

from baserow.contrib.database.fields.models import DateField
from baserow.contrib.database.fields.models import Field as BaserowField
from baserow.contrib.database.fields.models import (
    FormulaField,
    LinkRowField,
    LookupField,
    MultipleSelectField,
    NumberField,
    RatingField,
    SingleSelectField,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow_enterprise.assistant.types import BaseModel
from baserow_enterprise.data_sync.hubspot_contacts_data_sync import LongTextField


class FieldItemCreate(BaseModel):
    """Base model for creating a new field (no ID)."""

    name: str = Field(...)
    type: str = Field(...)

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        return {k: v for k, v in self.model_dump().items() if k not in {"id", "type"}}


class FieldItem(FieldItemCreate):
    """Model for an existing field (with ID)."""

    id: int = Field(...)

    @classmethod
    def from_django_orm(cls, orm_field: BaserowField) -> "FieldItem":
        return cls(
            id=orm_field.id,
            name=orm_field.name,
            type=field_type_registry.get_by_model(orm_field).type,
        )


# Event if type could be inferred, certain models (i.e. openai-gpt-oss-120b) requires
# all the fields to be required and can cause issues with optional fields, so we
# explicitly set them as required, even if seems unnecessary.


class BaseTextFieldItem(FieldItemCreate):
    type: Literal["text"] = Field(..., description="Single line text field.")


class TextFieldItemCreate(BaseTextFieldItem):
    """Model for creating a text field."""


class TextFieldItem(BaseTextFieldItem, FieldItem):
    """Model for an existing text field."""


class BaseLongTextFieldItem(FieldItemCreate):
    type: Literal["long_text"] = Field(
        ...,
        description="Multi-line text field. Ideal for descriptions, notes and long-form content.",
    )
    rich_text: bool = Field(
        default=True,
        description="Whether the long text field supports rich text.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        return {
            "name": self.name,
            "long_text_enable_rich_text": self.rich_text,
        }


class LongTextFieldItemCreate(BaseLongTextFieldItem):
    """Model for creating a long text field."""


class LongTextFieldItem(BaseLongTextFieldItem, FieldItem):
    """Model for an existing long text field."""

    @classmethod
    def from_django_orm(cls, orm_field: LongTextField) -> "LongTextFieldItem":
        field = orm_field.specific
        return cls(
            id=field.id,
            name=field.name,
            type="long_text",
            rich_text=orm_field.long_text_enable_rich_text,
        )


class BaseNumberFieldItem(FieldItemCreate):
    type: Literal["number"] = Field(
        ..., description="Numeric field, with decimals and optional prefix/suffix."
    )
    decimal_places: int = Field(default=2, description="The number of decimal places.")
    suffix: str = Field(
        default="",
        description="An optional suffix to display after the number.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        return {
            "name": self.name,
            "number_decimal_places": self.decimal_places,
            "number_suffix": self.suffix,
        }


class NumberFieldItemCreate(BaseNumberFieldItem):
    """Model for creating a number field."""


class NumberFieldItem(BaseNumberFieldItem, FieldItem):
    """Model for an existing number field."""

    @classmethod
    def from_django_orm(cls, orm_field: NumberField) -> "NumberFieldItem":
        return cls(
            id=orm_field.id,
            name=orm_field.name,
            type="number",
            decimal_places=orm_field.number_decimal_places,
            suffix=orm_field.number_suffix,
        )


class BaseRatingFieldItem(FieldItemCreate):
    type: Literal["rating"] = Field(
        ..., description="Rating field. Ideal for reviews or scores."
    )
    max_value: int = Field(
        default=5, description="The maximum value of the rating field."
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        return {
            "name": self.name,
            "max_value": self.max_value,
        }


class RatingFieldItemCreate(BaseRatingFieldItem):
    """Model for creating a rating field."""


class RatingFieldItem(BaseRatingFieldItem, FieldItem):
    """Model for an existing rating field."""

    @classmethod
    def from_django_orm(cls, orm_field: RatingField) -> "RatingFieldItem":
        return cls(
            id=orm_field.id,
            name=orm_field.name,
            type="rating",
            max_value=orm_field.max_value,
        )


class BaseBooleanFieldItem(FieldItemCreate):
    type: Literal["boolean"] = Field(..., description="Boolean field.")


class BooleanFieldItemCreate(BaseBooleanFieldItem):
    """Model for creating a boolean field."""


class BooleanFieldItem(BaseBooleanFieldItem, FieldItem):
    """Model for an existing boolean field."""


class BaseDateFieldItem(FieldItemCreate):
    type: Literal["date"] = Field(..., description="Date or datetime field.")
    include_time: bool = Field(
        default=False, description="Whether the date field includes time."
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        return {
            "name": self.name,
            "date_include_time": self.include_time,
        }


class DateFieldItemCreate(BaseDateFieldItem):
    """Model for creating a date field."""


class DateFieldItem(BaseDateFieldItem, FieldItem):
    """Model for an existing date field."""

    @classmethod
    def from_django_orm(cls, orm_field: DateField) -> "DateFieldItem":
        return cls(
            id=orm_field.id,
            name=orm_field.name,
            type="date",
            include_time=orm_field.date_include_time,
        )


class BaseLinkRowFieldItem(FieldItemCreate):
    type: Literal["link_row"] = Field(
        ..., description="Link row field. It creates relationships between tables."
    )
    linked_table: str | int = Field(
        ..., description="The ID or the name of the table this field links to."
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        if isinstance(self.linked_table, str):
            q = Q(name=self.linked_table, database=table.database)
        else:
            q = Q(id=self.linked_table, database=table.database)

        try:
            link_row_table = Table.objects.get(q)
        except Table.DoesNotExist:
            raise ValueError(
                f"The linked_table '{self.linked_table}' does not exist in the database."
                "Ensure you provide a valid table name or ID."
            )

        return {"name": self.name, "link_row_table": link_row_table}


class LinkRowFieldItemCreate(BaseLinkRowFieldItem):
    """Model for creating a link row field."""


class LinkRowFieldItem(BaseLinkRowFieldItem, FieldItem):
    """Model for an existing link row field."""

    @classmethod
    def from_django_orm(cls, orm_field: LinkRowField) -> "BaseLinkRowFieldItem":
        return cls(
            id=orm_field.id,
            name=orm_field.name,
            type="link_row",
            linked_table=orm_field.link_row_table_id,
        )


OptionColor = Literal[
    "light-blue",
    "light-green",
    "light-cyan",
    "light-orange",
    "light-yellow",
    "light-red",
    "light-brown",
    "light-purple",
    "light-pink",
    "light-gray",
    "blue",
    "green",
    "cyan",
    "orange",
    "yellow",
    "red",
    "brown",
    "purple",
    "pink",
    "gray",
    "dark-blue",
    "dark-green",
    "dark-cyan",
    "dark-orange",
    "dark-yellow",
    "dark-red",
    "dark-brown",
    "dark-purple",
    "dark-pink",
    "dark-gray",
    "darker-blue",
    "darker-green",
    "darker-cyan",
    "darker-orange",
    "darker-yellow",
    "darker-red",
    "darker-brown",
    "darker-purple",
    "darker-pink",
    "darker-gray",
    "deep-dark-green",
    "deep-dark-orange",
]


class SelectOption(BaseModel):
    id: int | None = Field(..., description="The unique identifier of the option.")
    value: str
    color: OptionColor


# Define a subset of colors to use when creating fields, so we don't confuse the model
# with too many options.
OptionColorCreate = Literal[
    "blue",
    "green",
    "cyan",
    "orange",
    "yellow",
    "red",
    "brown",
    "purple",
    "pink",
    "gray",
]


class SelectOptionCreate(BaseModel):
    value: str
    color: OptionColorCreate


class BaseSingleSelectFieldItem(FieldItemCreate):
    type: Literal["single_select"] = Field(
        ...,
        description="Single select field. Allows users to choose one option from a list.",
    )


class SingleSelectFieldItemCreate(BaseSingleSelectFieldItem):
    options: list[SelectOptionCreate] = Field(
        description="The list of options for the field. Use appropriate colors for each option.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        return {
            "name": self.name,
            "select_options": [
                {"id": -i, "value": option.value, "color": option.color}
                for (i, option) in enumerate(self.options, start=1)
            ],
        }


class SingleSelectFieldItem(BaseSingleSelectFieldItem, FieldItem):
    options: list[SelectOption] = Field(
        description="The list of options for the field.",
    )

    @classmethod
    def from_django_orm(
        cls, orm_field: SingleSelectField
    ) -> "BaseSingleSelectFieldItem":
        field = orm_field.specific
        return cls(
            id=field.id,
            name=field.name,
            type="single_select",
            options=[
                SelectOption(
                    id=opt.id,
                    value=opt.value,
                    color=opt.color,
                )
                for opt in field.select_options.all()
            ],
        )


class BaseMultipleSelectFieldItem(FieldItemCreate):
    type: Literal["multiple_select"] = Field(
        ...,
        description="Multiple select field. Allows users to choose multiple options from a list.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        return {
            "name": self.name,
            "select_options": [
                {"id": -i, "value": option.value, "color": option.color}
                for (i, option) in enumerate(self.options, start=1)
            ],
        }


class MultipleSelectFieldItemCreate(BaseMultipleSelectFieldItem):
    options: list[SelectOptionCreate] = Field(
        description="The list of options for the field. Use appropriate colors for each option.",
    )


class MultipleSelectFieldItem(BaseMultipleSelectFieldItem, FieldItem):
    options: list[SelectOption] = Field(
        description="The list of options for the field.",
    )

    @classmethod
    def from_django_orm(
        cls, orm_field: MultipleSelectField
    ) -> "BaseMultipleSelectFieldItem":
        field = orm_field.specific
        return cls(
            id=field.id,
            name=field.name,
            type="multiple_select",
            options=[
                SelectOption(
                    id=opt.id,
                    value=opt.value,
                    color=opt.color,
                )
                for opt in field.select_options.all()
            ],
        )


class BaseFileFieldItem(FieldItemCreate):
    type: Literal["file"] = Field(..., description="File field.")


class FileFieldItemCreate(BaseFileFieldItem):
    pass


class FileFieldItem(BaseFileFieldItem, FieldItem):
    pass


class FormulaFieldItemCreate(FieldItemCreate):
    type: Literal["formula"] = Field(..., description="Formula field.")
    formula: str = Field(
        ...,
        description="The formula to use in the field. It needs to be generated via the appropriate tool or use '' as placeholder.",
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        return {
            "name": self.name,
            "formula": self.formula,
        }


class FormulaFieldItem(FormulaFieldItemCreate, FieldItem):
    formula_type: str = Field(..., description="The type of the formula.")
    array_formula_type: str | None = Field(
        ...,
        description=("If the formula type is 'array', the type of the array items."),
    )

    @classmethod
    def from_django_orm(cls, orm_field: FormulaField) -> "FormulaFieldItem":
        field = orm_field.specific
        return cls(
            id=field.id,
            name=field.name,
            type="formula",
            formula=field.formula,
            formula_type=field.formula_type,
            array_formula_type=field.array_formula_type,
        )


class LookupFieldItemCreate(FieldItemCreate):
    type: Literal["lookup"] = Field(..., description="Lookup field.")
    through_field: int | str = Field(
        ..., description="The ID of the link row field to lookup through."
    )
    target_field: int | str = Field(
        ..., description="The ID of the field to lookup on the linked table."
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, any]:
        data = {"name": self.name}
        if isinstance(self.through_field, str):
            data["through_field_name"] = self.through_field
        else:
            data["through_field_id"] = self.through_field

        if isinstance(self.target_field, str):
            data["target_field_name"] = self.target_field
        else:
            data["target_field_id"] = self.target_field

        return data


class LookupFieldItem(LookupFieldItemCreate, FieldItem):
    through_field_name: str = Field(
        ..., description="The name of the link row field to lookup through."
    )
    target_field_name: str = Field(
        ..., description="The name of the field to lookup on the linked table."
    )

    @classmethod
    def from_django_orm(cls, orm_field: LookupField) -> "LookupFieldItem":
        field = orm_field.specific
        return cls(
            id=field.id,
            name=field.name,
            type="lookup",
            through_field=field.through_field_id,
            target_field=field.target_field_id,
            through_field_name=field.through_field_name,
            target_field_name=field.target_field_name,
        )


AnyFieldItemCreate = Annotated[
    TextFieldItemCreate
    | LongTextFieldItemCreate
    | NumberFieldItemCreate
    | RatingFieldItemCreate
    | BooleanFieldItemCreate
    | DateFieldItemCreate
    | LinkRowFieldItemCreate
    | SingleSelectFieldItemCreate
    | MultipleSelectFieldItemCreate
    | FileFieldItemCreate
    | FormulaFieldItemCreate
    | LookupFieldItemCreate,
    Field(discriminator="type"),
]

AnyFieldItem = (
    TextFieldItem
    | LongTextFieldItem
    | NumberFieldItem
    | RatingFieldItem
    | BooleanFieldItem
    | DateFieldItem
    | LinkRowFieldItem
    | SingleSelectFieldItem
    | MultipleSelectFieldItem
    | FileFieldItem
    | FormulaFieldItem
    | LookupFieldItem
    | FieldItem
)


class FieldItemsRegistry:
    _registry = {
        "text": TextFieldItem,
        "long_text": LongTextFieldItem,
        "number": NumberFieldItem,
        "date": DateFieldItem,
        "boolean": BooleanFieldItem,
        "rating": RatingFieldItem,
        "link_row": LinkRowFieldItem,
        "single_select": SingleSelectFieldItem,
        "multiple_select": MultipleSelectFieldItem,
        "file": FileFieldItem,
        "formula": FormulaFieldItem,
        "lookup": LookupFieldItem,
    }

    def from_django_orm(self, orm_field: Type[BaserowField]) -> FieldItem:
        field_type = field_type_registry.get_by_model(orm_field).type
        field_class: FieldItem = self._registry.get(field_type, FieldItem)
        return field_class.from_django_orm(orm_field)


field_item_registry = FieldItemsRegistry()
