import json
from typing import Any, Literal

from django.db.models import Q

from pydantic import Field, model_serializer, model_validator

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
    color: OptionColorCreate | None = None


class InvalidFormulaFieldError(Exception):
    """Raised when a formula field has an invalid formula."""

    def __init__(self, field_name: str, formula: str, table: Table, error: str):
        self.field_name = field_name
        self.formula = formula
        self.table = table
        self.error = error
        super().__init__(f"Invalid formula for field '{field_name}': {error}")


# ---------------------------------------------------------------------------
# Flat field types — single model, all type-specific fields optional
# ---------------------------------------------------------------------------

FieldType = Literal[
    "text",
    "long_text",
    "number",
    "rating",
    "boolean",
    "date",
    "link_row",
    "single_select",
    "multiple_select",
    "file",
    "formula",
    "lookup",
]

_TYPE_ALIASES: dict[str, str] = {
    "string": "text",
    "varchar": "text",
    "rich_text": "long_text",
    "richtext": "long_text",
    "textarea": "long_text",
    "integer": "number",
    "int": "number",
    "float": "number",
    "decimal": "number",
    "numeric": "number",
    "checkbox": "boolean",
    "bool": "boolean",
    "datetime": "date",
    "link": "link_row",
    "relation": "link_row",
    "relationship": "link_row",
    "foreign_key": "link_row",
    "fk": "link_row",
    "select": "single_select",
    "dropdown": "single_select",
    "enum": "single_select",
    "multi_select": "multiple_select",
    "multiselect": "multiple_select",
    "tags": "multiple_select",
    "attachment": "file",
    "upload": "file",
    "image": "file",
}

_SELECT_COLORS: list[str] = [
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

_KEY_ALIASES: dict[str, str] = {
    "long_text_enable_rich_text": "rich_text",
    "number_decimal_places": "decimal_places",
    "number_suffix": "suffix",
    "date_include_time": "include_time",
    "link_row_table": "linked_table",
    "link_row_table_id": "linked_table",
    "through_field": "linked_table",
    "through_field_id": "linked_table",
    "target_field_id": "target_field",
}

# Creation order: regular → link_row → lookup → formula
FIELD_ORDER: dict[str, int] = {"link_row": 1, "lookup": 2, "formula": 3}

_FIELD_EXAMPLES: dict[str, dict] = {
    "text": {"name": "Title", "type": "text"},
    "long_text": {"name": "Notes", "type": "long_text"},
    "number": {"name": "Price", "type": "number", "decimal_places": 2},
    "rating": {"name": "Stars", "type": "rating", "max_value": 5},
    "boolean": {"name": "Active", "type": "boolean"},
    "date": {"name": "Due Date", "type": "date"},
    "link_row": {
        "name": "Project",
        "type": "link_row",
        "linked_table": "Projects",
    },
    "single_select": {
        "name": "Status",
        "type": "single_select",
        "options": [{"value": "Open", "color": "green"}],
    },
    "multiple_select": {
        "name": "Tags",
        "type": "multiple_select",
        "options": [{"value": "Important", "color": "red"}],
    },
    "file": {"name": "Attachment", "type": "file"},
    "formula": {
        "name": "Total",
        "type": "formula",
        "formula": "field('Price') * 2",
    },
    "lookup": {
        "name": "Client Name",
        "type": "lookup",
        "linked_table": "Clients",
        "target_field": "Name",
    },
}


# ---------------------------------------------------------------------------
# to_django_orm builders: (FieldItemCreate, Table, user | None) -> dict
# ---------------------------------------------------------------------------


def _resolve_linked_table(linked_table_ref, table):
    """Resolve a linked_table reference (name or ID) to a Table object."""

    if isinstance(linked_table_ref, str):
        q = Q(name=linked_table_ref, database=table.database)
    else:
        q = Q(id=linked_table_ref, database=table.database)
    result = Table.objects.filter(q).order_by("id").first()
    if not result:
        raise ValueError(
            f"Table '{linked_table_ref}' not found in the database. "
            f"Ensure you provide a valid table name or ID."
        )
    return result


def _simple_to_orm(f, table, user):
    return {"name": f.name}


def _long_text_to_orm(f, table, user):
    return {"name": f.name, "long_text_enable_rich_text": f.rich_text}


def _number_to_orm(f, table, user):
    return {
        "name": f.name,
        "number_decimal_places": f.decimal_places,
        "number_suffix": f.suffix,
        "number_negative": True,
    }


def _rating_to_orm(f, table, user):
    return {"name": f.name, "max_value": f.max_value}


def _date_to_orm(f, table, user):
    return {"name": f.name, "date_include_time": f.include_time}


def _link_row_to_orm(f, table, user):
    linked = _resolve_linked_table(f.linked_table, table)
    return {"name": f.name, "link_row_table": linked}


def _select_to_orm(f, table, user):
    return {
        "name": f.name,
        "select_options": [
            {
                "id": -i,
                "value": opt.value,
                "color": opt.color or _SELECT_COLORS[(i - 1) % len(_SELECT_COLORS)],
            }
            for i, opt in enumerate(f.options, start=1)
        ],
    }


def _formula_to_orm(f, table, user):
    if f.formula:
        from baserow.contrib.database.fields.models import FormulaField
        from baserow.core.formula.parser.exceptions import BaserowFormulaException

        try:
            tmp = FormulaField(formula=f.formula, table=table, name=f.name, order=0)
            tmp.recalculate_internal_fields(raise_if_invalid=True)
        except BaserowFormulaException as e:
            raise InvalidFormulaFieldError(f.name, f.formula, table, str(e))

    return {"name": f.name, "formula": f.formula}


def _lookup_to_orm(f, table, user):
    from baserow.contrib.database.fields.models import LinkRowField

    linked = _resolve_linked_table(f.linked_table, table)

    # Find existing link_row field pointing to linked table
    through = (
        LinkRowField.objects.filter(table=table, link_row_table=linked)
        .order_by("id")
        .first()
    )

    # Auto-create link_row if missing and user is available
    if not through and user:
        from baserow.contrib.database.fields.actions import CreateFieldActionType

        through = CreateFieldActionType.do(
            user,
            table,
            "link_row",
            name=linked.name,
            link_row_table=linked,
        )

    if not through:
        raise ValueError(
            f"No link_row field to '{f.linked_table}' exists on this table. "
            f"Create a link_row field first."
        )

    data: dict[str, Any] = {"name": f.name, "through_field_id": through.id}
    if isinstance(f.target_field, str):
        data["target_field_name"] = f.target_field
    else:
        data["target_field_id"] = f.target_field
    return data


_TO_DJANGO_ORM = {
    "text": _simple_to_orm,
    "boolean": _simple_to_orm,
    "file": _simple_to_orm,
    "long_text": _long_text_to_orm,
    "number": _number_to_orm,
    "rating": _rating_to_orm,
    "date": _date_to_orm,
    "link_row": _link_row_to_orm,
    "single_select": _select_to_orm,
    "multiple_select": _select_to_orm,
    "formula": _formula_to_orm,
    "lookup": _lookup_to_orm,
}


# ---------------------------------------------------------------------------
# from_django_orm builders: (orm_field) -> dict of extra kwargs
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


_FROM_DJANGO_ORM: dict[str, Any] = {
    "long_text": lambda f: {"rich_text": f.specific.long_text_enable_rich_text},
    "number": lambda f: {
        "decimal_places": f.number_decimal_places,
        "suffix": f.number_suffix,
    },
    "rating": lambda f: {"max_value": f.max_value},
    "date": lambda f: {"include_time": f.date_include_time},
    "link_row": lambda f: {"linked_table": f.link_row_table_id},
    "single_select": lambda f: {"options": _select_options_from_orm(f)},
    "multiple_select": lambda f: {"options": _select_options_from_orm(f)},
    "formula": lambda f: {
        "formula": f.specific.formula,
        "formula_type": f.specific.formula_type,
        "array_formula_type": f.specific.array_formula_type,
    },
    "lookup": lambda f: {
        "through_field": f.specific.through_field_id,
        "target_field": f.specific.target_field_id,
        "through_field_name": f.specific.through_field_name,
        "target_field_name": f.specific.target_field_name,
    },
}


# ---------------------------------------------------------------------------
# FieldItemCreate
# ---------------------------------------------------------------------------


class FieldItemCreate(BaseModel):
    """Flat model for creating a field: name + type + type-specific options."""

    name: str = Field(..., description="The name of the field.")
    type: FieldType = Field(..., description="The field type.")

    # (long_text)
    rich_text: bool = Field(
        True, description="(long_text) Whether the field supports rich text."
    )
    # (number)
    decimal_places: int = Field(
        0, description="(number) Decimal places (0, 1, 2, ...)."
    )
    suffix: str = Field(
        "", description="(number) Suffix displayed after the number, or ''."
    )
    # (rating)
    max_value: int = Field(5, description="(rating) Maximum rating value.")
    # (date)
    include_time: bool = Field(
        False, description="(date) Whether the date includes time."
    )
    # (link_row, lookup)
    linked_table: str | int | None = Field(
        None,
        description="(link_row, lookup) ID or name of the linked table.",
    )
    # (single_select, multiple_select)
    options: list[SelectOptionCreate] | None = Field(
        None,
        description="(single_select, multiple_select) List of options with colors.",
    )
    # (formula)
    formula: str = Field(
        "", description="(formula) The formula expression, or '' as placeholder."
    )
    # (lookup)
    target_field: int | str | None = Field(
        None, description="(lookup) ID or name of the field to look up."
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize(cls, data):
        if not isinstance(data, dict):
            return data

        # Normalize type aliases
        raw_type = data.get("type")
        if isinstance(raw_type, str):
            data["type"] = _TYPE_ALIASES.get(raw_type, raw_type)

        # Normalize key aliases
        for old_key, new_key in _KEY_ALIASES.items():
            if old_key in data and new_key not in data:
                data[new_key] = data.pop(old_key)

        # Convert string options to SelectOptionCreate dicts
        if "options" in data and isinstance(data["options"], list):
            normalized = []
            for i, opt in enumerate(data["options"]):
                if isinstance(opt, str):
                    normalized.append(
                        {"value": opt, "color": _SELECT_COLORS[i % len(_SELECT_COLORS)]}
                    )
                else:
                    normalized.append(opt)
            data["options"] = normalized

        return data

    # Required fields per type: {type: [(attr_name, display_name), ...]}
    _REQUIRED_FIELDS: dict[str, list[tuple[str, str]]] = {
        "link_row": [("linked_table", "linked_table")],
        "single_select": [("options", "options")],
        "multiple_select": [("options", "options")],
        "lookup": [("linked_table", "linked_table"), ("target_field", "target_field")],
    }

    @model_validator(mode="after")
    def _validate_required_for_type(self):
        required = self._REQUIRED_FIELDS.get(self.type)
        if required:
            missing = [name for attr, name in required if not getattr(self, attr)]
            if missing:
                raise ValueError(
                    f"{self.type} requires {', '.join(missing)}. "
                    f"Example: {json.dumps(_FIELD_EXAMPLES[self.type])}"
                )
        return self

    def to_django_orm_kwargs(self, table: Table, user=None) -> dict[str, Any]:
        builder = _TO_DJANGO_ORM.get(self.type, _simple_to_orm)
        return builder(self, table, user)


# ---------------------------------------------------------------------------
# FieldItem (read-back)
# ---------------------------------------------------------------------------


class FieldItem(BaseModel):
    """Existing field with ID — flat structure matching FieldItemCreate."""

    id: int = Field(...)
    name: str = Field(..., description="The name of the field.")
    type: str = Field(..., description="The field type.")

    # Type-specific (populated per type, others excluded via exclude_none)
    rich_text: bool | None = None
    decimal_places: int | None = None
    suffix: str | None = None
    max_value: int | None = None
    include_time: bool | None = None
    linked_table: int | None = None
    options: list[SelectOption] | None = None
    formula: str | None = None
    formula_type: str | None = None
    array_formula_type: str | None = None
    through_field: int | None = None
    target_field: int | None = None
    through_field_name: str | None = None
    target_field_name: str | None = None

    @model_serializer(mode="wrap")
    def _exclude_none(self, handler):
        return {k: v for k, v in handler(self).items() if v is not None}

    @classmethod
    def from_django_orm(cls, orm_field: BaserowField) -> "FieldItem":
        field_type = field_type_registry.get_by_model(orm_field).type
        kwargs: dict[str, Any] = {
            "id": orm_field.id,
            "name": orm_field.name,
            "type": field_type,
        }
        builder = _FROM_DJANGO_ORM.get(field_type)
        if builder:
            kwargs.update(builder(orm_field))
        return cls(**kwargs)


# ---------------------------------------------------------------------------
# FieldItemUpdate
# ---------------------------------------------------------------------------


def _update_simple(f, field_type):
    kwargs = {}
    if f.name is not None:
        kwargs["name"] = f.name
    return kwargs


def _update_long_text(f, field_type):
    kwargs = _update_simple(f, field_type)
    if f.rich_text is not None:
        kwargs["long_text_enable_rich_text"] = f.rich_text
    return kwargs


def _update_number(f, field_type):
    kwargs = _update_simple(f, field_type)
    if f.decimal_places is not None:
        kwargs["number_decimal_places"] = f.decimal_places
    if f.suffix is not None:
        kwargs["number_suffix"] = f.suffix
    return kwargs


def _update_rating(f, field_type):
    kwargs = _update_simple(f, field_type)
    if f.max_value is not None:
        kwargs["max_value"] = f.max_value
    return kwargs


def _update_date(f, field_type):
    kwargs = _update_simple(f, field_type)
    if f.include_time is not None:
        kwargs["date_include_time"] = f.include_time
    return kwargs


def _update_select(f, field_type):
    kwargs = _update_simple(f, field_type)
    if f.options is not None:
        kwargs["select_options"] = [
            {
                "id": -i,
                "value": opt.value,
                "color": opt.color or _SELECT_COLORS[(i - 1) % len(_SELECT_COLORS)],
            }
            for i, opt in enumerate(f.options, start=1)
        ]
    return kwargs


def _update_formula(f, field_type):
    kwargs = _update_simple(f, field_type)
    if f.formula is not None:
        kwargs["formula"] = f.formula
    return kwargs


_TO_UPDATE_ORM = {
    "text": _update_simple,
    "boolean": _update_simple,
    "file": _update_simple,
    "long_text": _update_long_text,
    "number": _update_number,
    "rating": _update_rating,
    "date": _update_date,
    "link_row": _update_simple,
    "single_select": _update_select,
    "multiple_select": _update_select,
    "formula": _update_formula,
    "lookup": _update_simple,
}


class FieldItemUpdate(BaseModel):
    """Flat model for updating a field: field_id + optional type-specific fields."""

    field_id: int = Field(..., description="The ID of the field to update.")
    name: str | None = Field(None, description="New name for the field.")

    # (long_text)
    rich_text: bool | None = Field(
        None, description="(long_text) Whether the field supports rich text."
    )
    # (number)
    decimal_places: int | None = Field(
        None, description="(number) Decimal places (0, 1, 2, ...)."
    )
    suffix: str | None = Field(
        None, description="(number) Suffix displayed after the number."
    )
    # (rating)
    max_value: int | None = Field(None, description="(rating) Maximum rating value.")
    # (date)
    include_time: bool | None = Field(
        None, description="(date) Whether the date includes time."
    )
    # (single_select, multiple_select)
    options: list[SelectOptionCreate] | None = Field(
        None,
        description="(single_select, multiple_select) List of options with colors.",
    )
    # (formula)
    formula: str | None = Field(None, description="(formula) The formula expression.")

    @model_validator(mode="before")
    @classmethod
    def _normalize_keys(cls, data):
        if not isinstance(data, dict):
            return data
        for old_key, new_key in _KEY_ALIASES.items():
            if old_key in data and new_key not in data:
                data[new_key] = data.pop(old_key)
        # Convert string options to SelectOptionCreate dicts
        if "options" in data and isinstance(data["options"], list):
            normalized = []
            for i, opt in enumerate(data["options"]):
                if isinstance(opt, str):
                    normalized.append(
                        {"value": opt, "color": _SELECT_COLORS[i % len(_SELECT_COLORS)]}
                    )
                else:
                    normalized.append(opt)
            data["options"] = normalized
        return data

    def to_update_kwargs(self, field_type: str) -> dict[str, Any]:
        """Build kwargs for UpdateFieldActionType.do() based on the field's current type."""
        builder = _TO_UPDATE_ORM.get(field_type, _update_simple)
        return builder(self, field_type)
