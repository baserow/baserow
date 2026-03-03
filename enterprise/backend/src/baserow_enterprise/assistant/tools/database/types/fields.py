from typing import Any, Callable, Literal

from django.db.models import Q

from pydantic import Field

from baserow.contrib.database.fields.models import Field as BaserowField
from baserow.contrib.database.fields.registries import field_type_registry
from baserow_enterprise.assistant.types import BaseModel
from baserow_premium.permission_manager import Table

# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

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


# Subset of colors for creation to avoid confusing the model
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


class InvalidFormulaFieldError(Exception):
    """Raised when a formula field has an invalid formula."""

    def __init__(self, field_name: str, formula: str, table: Table, error: str):
        self.field_name = field_name
        self.formula = formula
        self.table = table
        self.error = error
        super().__init__(f"Invalid formula for field '{field_name}': {error}")


# ---------------------------------------------------------------------------
# Type-specific config models (each has a `type` literal)
#
# Create configs have `to_django_orm_kwargs` for field creation.
# Read configs extend create configs where extras are needed.
# ---------------------------------------------------------------------------


class TextConfig(BaseModel):
    type: Literal["text"] = Field(..., description="Must be 'text'.")

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        return {"name": name}


class LongTextConfig(BaseModel):
    type: Literal["long_text"] = Field(..., description="Must be 'long_text'.")
    rich_text: bool = Field(
        ..., description="Whether the field supports rich text. Typically true."
    )

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        return {"name": name, "long_text_enable_rich_text": self.rich_text}


class NumberConfig(BaseModel):
    type: Literal["number"] = Field(..., description="Must be 'number'.")
    decimal_places: int = Field(
        ..., description="The number of decimal places (e.g. 0, 1, 2)."
    )
    suffix: str = Field(
        ..., description="A suffix to display after the number, or '' for none."
    )

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        return {
            "name": name,
            "number_decimal_places": self.decimal_places,
            "number_suffix": self.suffix,
            "number_negative": True,
        }


class RatingConfig(BaseModel):
    type: Literal["rating"] = Field(..., description="Must be 'rating'.")
    max_value: int = Field(..., description="The maximum rating value (e.g. 5).")

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        return {"name": name, "max_value": self.max_value}


class BooleanConfig(BaseModel):
    type: Literal["boolean"] = Field(..., description="Must be 'boolean'.")

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        return {"name": name}


class DateConfig(BaseModel):
    type: Literal["date"] = Field(..., description="Must be 'date'.")
    include_time: bool = Field(..., description="Whether the date field includes time.")

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        return {"name": name, "date_include_time": self.include_time}


class LinkRowConfig(BaseModel):
    type: Literal["link_row"] = Field(..., description="Must be 'link_row'.")
    linked_table: str | int = Field(
        ..., description="The ID or name of the table this field links to."
    )

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        if isinstance(self.linked_table, str):
            q = Q(name=self.linked_table, database=table.database)
        else:
            q = Q(id=self.linked_table, database=table.database)

        link_row_table = Table.objects.filter(q).order_by("id").first()
        if not link_row_table:
            raise ValueError(
                f"The linked_table '{self.linked_table}' does not exist in the database."
                "Ensure you provide a valid table name or ID."
            )
        return {"name": name, "link_row_table": link_row_table}


class SingleSelectConfig(BaseModel):
    type: Literal["single_select"] = Field(..., description="Must be 'single_select'.")
    options: list[SelectOptionCreate] = Field(
        ..., description="The list of options with colors."
    )

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        return {
            "name": name,
            "select_options": [
                {"id": -i, "value": option.value, "color": option.color}
                for (i, option) in enumerate(self.options, start=1)
            ],
        }


class MultipleSelectConfig(BaseModel):
    type: Literal["multiple_select"] = Field(
        ..., description="Must be 'multiple_select'."
    )
    options: list[SelectOptionCreate] = Field(
        ..., description="The list of options with colors."
    )

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        return {
            "name": name,
            "select_options": [
                {"id": -i, "value": option.value, "color": option.color}
                for (i, option) in enumerate(self.options, start=1)
            ],
        }


class FileConfig(BaseModel):
    type: Literal["file"] = Field(..., description="Must be 'file'.")

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        return {"name": name}


class FormulaConfig(BaseModel):
    type: Literal["formula"] = Field(..., description="Must be 'formula'.")
    formula: str = Field(
        ..., description="The formula expression, or '' as placeholder."
    )

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        if self.formula:
            from baserow.contrib.database.fields.models import FormulaField
            from baserow.core.formula.parser.exceptions import BaserowFormulaException

            try:
                tmp = FormulaField(
                    formula=self.formula, table=table, name=name, order=0
                )
                tmp.recalculate_internal_fields(raise_if_invalid=True)
            except BaserowFormulaException as e:
                raise InvalidFormulaFieldError(name, self.formula, table, str(e))

        return {"name": name, "formula": self.formula}


class LookupConfig(BaseModel):
    type: Literal["lookup"] = Field(..., description="Must be 'lookup'.")
    through_field: int | str = Field(
        ..., description="The ID or name of the link row field to look through."
    )
    target_field: int | str = Field(
        ..., description="The ID or name of the field to look up."
    )

    def to_django_orm_kwargs(self, name: str, table: Table) -> dict[str, Any]:
        data = {"name": name}
        if isinstance(self.through_field, str):
            data["through_field_name"] = self.through_field
        else:
            data["through_field_id"] = self.through_field

        if isinstance(self.target_field, str):
            data["target_field_name"] = self.target_field
        else:
            data["target_field_id"] = self.target_field
        return data


# ---------------------------------------------------------------------------
# Read-back config variants (extend create configs where extras are needed)
# ---------------------------------------------------------------------------


class SingleSelectReadConfig(BaseModel):
    """Read-back variant with full SelectOption (including id)."""

    type: Literal["single_select"] = "single_select"
    options: list[SelectOption]


class MultipleSelectReadConfig(BaseModel):
    """Read-back variant with full SelectOption (including id)."""

    type: Literal["multiple_select"] = "multiple_select"
    options: list[SelectOption]


class FormulaReadConfig(FormulaConfig):
    """Read-back variant with computed formula metadata."""

    formula_type: str | None = None
    array_formula_type: str | None = None


class LookupReadConfig(LookupConfig):
    """Read-back variant with resolved field names."""

    through_field_name: str | None = None
    target_field_name: str | None = None


class GenericFieldConfig(BaseModel):
    """Fallback for field types not in our supported set."""

    type: str


# ---------------------------------------------------------------------------
# Config type unions
# ---------------------------------------------------------------------------

# Create config union (LLM-facing) — anyOf for broader LLM compatibility
AnyFieldConfig = (
    TextConfig
    | LongTextConfig
    | NumberConfig
    | RatingConfig
    | BooleanConfig
    | DateConfig
    | LinkRowConfig
    | SingleSelectConfig
    | MultipleSelectConfig
    | FileConfig
    | FormulaConfig
    | LookupConfig
)

# Read config union — includes read variants and a generic fallback
AnyFieldReadConfig = (
    TextConfig
    | LongTextConfig
    | NumberConfig
    | RatingConfig
    | BooleanConfig
    | DateConfig
    | LinkRowConfig
    | SingleSelectReadConfig
    | MultipleSelectReadConfig
    | FileConfig
    | FormulaReadConfig
    | LookupReadConfig
    | GenericFieldConfig
)


# ---------------------------------------------------------------------------
# Field item models (shared base, consistent structure)
# ---------------------------------------------------------------------------


class _FieldItemBase(BaseModel):
    """Shared base for create and read-back field models."""

    name: str = Field(..., description="The name of the field.")


class FieldItemCreate(_FieldItemBase):
    """Model for creating a field: name + config."""

    config: AnyFieldConfig = Field(
        ..., description="Type and configuration of the field."
    )

    def to_django_orm_kwargs(self, table: Table) -> dict[str, Any]:
        return self.config.to_django_orm_kwargs(self.name, table)


# ---------------------------------------------------------------------------
# Read-back model (config-based, consistent with FieldItemCreate)
# ---------------------------------------------------------------------------


def _select_options_from_orm(orm_field):
    from typing import get_args

    valid_colors = set(get_args(OptionColor))
    return [
        SelectOption(
            id=opt.id,
            value=opt.value,
            color=opt.color if opt.color in valid_colors else "blue",
        )
        for opt in orm_field.specific.select_options.all()
    ]


_CONFIG_BUILDERS: dict[str, Callable] = {
    "text": lambda f: TextConfig(type="text"),
    "long_text": lambda f: LongTextConfig(
        type="long_text",
        rich_text=f.specific.long_text_enable_rich_text,
    ),
    "number": lambda f: NumberConfig(
        type="number",
        decimal_places=f.number_decimal_places,
        suffix=f.number_suffix,
    ),
    "rating": lambda f: RatingConfig(type="rating", max_value=f.max_value),
    "boolean": lambda f: BooleanConfig(type="boolean"),
    "date": lambda f: DateConfig(type="date", include_time=f.date_include_time),
    "link_row": lambda f: LinkRowConfig(
        type="link_row", linked_table=f.link_row_table_id
    ),
    "single_select": lambda f: SingleSelectReadConfig(
        type="single_select",
        options=_select_options_from_orm(f),
    ),
    "multiple_select": lambda f: MultipleSelectReadConfig(
        type="multiple_select",
        options=_select_options_from_orm(f),
    ),
    "file": lambda f: FileConfig(type="file"),
    "formula": lambda f: FormulaReadConfig(
        type="formula",
        formula=f.specific.formula,
        formula_type=f.specific.formula_type,
        array_formula_type=f.specific.array_formula_type,
    ),
    "lookup": lambda f: LookupReadConfig(
        type="lookup",
        through_field=f.specific.through_field_id,
        target_field=f.specific.target_field_id,
        through_field_name=f.specific.through_field_name,
        target_field_name=f.specific.target_field_name,
    ),
}


def _config_from_orm(field_type: str, orm_field) -> AnyFieldReadConfig:
    """Build the appropriate config object from a Django ORM field instance."""

    builder = _CONFIG_BUILDERS.get(field_type)
    if builder is None:
        return GenericFieldConfig(type=field_type)
    return builder(orm_field)


class FieldItem(_FieldItemBase):
    """Existing field with ID. Config-based, consistent with FieldItemCreate."""

    id: int = Field(...)
    config: AnyFieldReadConfig

    def model_dump(self, **kwargs):
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)

    @classmethod
    def from_django_orm(cls, orm_field: BaserowField) -> "FieldItem":
        field_type = field_type_registry.get_by_model(orm_field).type
        config = _config_from_orm(field_type, orm_field)
        return cls(id=orm_field.id, name=orm_field.name, config=config)


AnyFieldItem = FieldItem
