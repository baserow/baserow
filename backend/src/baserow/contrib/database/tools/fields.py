"""
Field tools shared by the clients that act for a user. A formula is stored as
written when it is valid. An invalid one is reported back, never repaired here,
so this module calls no model.
"""

import json
from typing import Annotated, Any, Literal, get_args

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.utils.translation import gettext as _

from pydantic import BaseModel as PydanticBaseModel
from pydantic import ConfigDict, Field, model_serializer, model_validator

from baserow.contrib.database.fields.actions import (
    CreateFieldActionType,
    DeleteFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.fields.exceptions import FailedToLockFieldDueToConflict
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field as BaserowField
from baserow.contrib.database.fields.models import (
    FormulaField,
    LinkRowField,
)
from baserow.contrib.database.fields.models import (
    SelectOption as BaserowSelectOption,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tools.errors import conflict_errors, user_error_message
from baserow.core.cache import local_cache
from baserow.core.exceptions import PermissionException
from baserow.core.formula.parser.exceptions import BaserowFormulaException
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import (
    ToolError,
    ToolErrorCode,
    classify_item_error,
    finish_batch,
    item_error,
)


class BaseModel(PydanticBaseModel):
    model_config = ConfigDict(extra="forbid", coerce_numbers_to_str=True)


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------


class SelectOption(BaseModel):
    id: int | None = Field(..., description="The unique identifier of the option.")
    value: str
    color: str


# Only the base colors are offered, to avoid confusing the model
OptionColor = Literal[
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
    value: str = Field(..., max_length=255)
    color: OptionColor | None = None


class SelectOptionUpdate(BaseModel):
    id: int = Field(..., description="ID of the option, from the table schema.")
    value: str | None = Field(
        None, max_length=255, description="New value. Omit to keep it."
    )
    color: OptionColor | None = Field(None, description="New color. Omit to keep it.")

    @model_validator(mode="after")
    def _require_a_change(self) -> "SelectOptionUpdate":
        if self.value is None and self.color is None:
            raise ValueError(f"Option {self.id} needs a new value or color.")
        return self


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

_SELECT_COLORS: list[str] = list(get_args(OptionColor))

_KEY_ALIASES: dict[str, str] = {
    "long_text_enable_rich_text": "rich_text",
    "number_decimal_places": "decimal_places",
    "number_suffix": "suffix",
    "date_include_time": "include_time",
    "link_row_table": "linked_table",
    "link_row_table_id": "linked_table",
    "through_field_id": "through_field",
    "target_field_id": "target_field",
}

# Marks a description of a formula, which is not a formula itself.
FORMULA_DESCRIPTION_PREFIX = "$formula:"

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


def _resolve_linked_table(linked_table_ref, table, user):
    """
    Resolve a linked_table reference (name or ID) to a table of the database the
    user can see. Hidden tables are left out, so an error never reveals one.
    """

    if isinstance(linked_table_ref, str):
        q = Q(name=linked_table_ref, database=table.database)
    else:
        q = Q(id=linked_table_ref, database=table.database)
    tables = TableHandler().list_workspace_tables(user, table.database.workspace)
    matches = list(tables.filter(q).order_by("id")[:2])
    if not matches:
        raise ValueError(
            f"Table '{linked_table_ref}' not found in the database. "
            f"Ensure you provide a valid table name or ID."
        )
    if len(matches) > 1:
        raise ValueError(
            f"Several tables in this database are named '{linked_table_ref}'. "
            "Use the table ID instead."
        )
    return matches[0]


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
    linked = _resolve_linked_table(f.linked_table, table, user)
    return {"name": f.name, "link_row_table": linked}


def _select_to_orm(f, table, user):
    options = [
        {
            "value": opt.value,
            "color": opt.color or _SELECT_COLORS[(i - 1) % len(_SELECT_COLORS)],
        }
        for i, opt in enumerate(f.options, start=1)
    ]
    _check_unique_values([], options, set(), hint="Give each option its own value.")
    return {
        "name": f.name,
        "select_options": [
            {"id": -i, **option} for i, option in enumerate(options, start=1)
        ],
    }


def check_formula(table: Table, field_name: str, formula: str) -> None:
    """
    Check that a formula is valid Baserow formula syntax for the table.

    :param table: The table the formula field belongs to.
    :param field_name: The name of the formula field.
    :param formula: The formula to check.
    :raises InvalidFormulaFieldError: With the parser message, or with a request
        for a formula when it is empty or a ``$formula:`` description is given
        instead.
    """

    if not formula.strip():
        raise InvalidFormulaFieldError(
            field_name, formula, table, f"'{field_name}' needs a formula."
        )
    if formula.strip().lower().startswith(FORMULA_DESCRIPTION_PREFIX):
        raise InvalidFormulaFieldError(
            field_name,
            formula,
            table,
            f"'{field_name}' needs a formula, not a description. Write it in "
            "Baserow formula syntax.",
        )
    try:
        tmp = FormulaField(formula=formula, table=table, name=field_name, order=0)
        tmp.recalculate_internal_fields(raise_if_invalid=True)
    except BaserowFormulaException as e:
        raise InvalidFormulaFieldError(field_name, formula, table, str(e))


def _formula_to_orm(f, table, user):
    formula = f.formula or ""
    check_formula(table, f.name, formula)
    return {"name": f.name, "formula": formula}


def _named_link_field(f, table, user) -> LinkRowField:
    """
    The link_row field of the table a lookup names in ``through_field``.

    :raises ValueError: When the table has no such link_row field, or it links to
        another table than ``linked_table``.
    """

    links = list(LinkRowField.objects.filter(table=table).order_by("id"))
    if isinstance(f.through_field, str):
        # Like select labels, an exact name wins, then case and outer spaces are
        # ignored.
        key = option_value_key(f.through_field)
        through = next((x for x in links if x.name == f.through_field), None) or next(
            (x for x in links if option_value_key(x.name) == key), None
        )
    else:
        through = next((x for x in links if x.id == f.through_field), None)
    if through is None:
        raise ValueError(
            f"Table '{table.name}' has no link_row field '{f.through_field}' for "
            f"lookup '{f.name}'."
        )
    if f.linked_table is not None:
        linked = _resolve_linked_table(f.linked_table, table, user)
        if linked.id != through.link_row_table_id:
            raise ValueError(
                f"Link field '{through.name}' links to table "
                f"{through.link_row_table_id}, not to '{f.linked_table}'."
            )
    return through


def _only_link_field(f, table) -> LinkRowField:
    """
    The table's link_row field, for a lookup that names neither ``linked_table``
    nor ``through_field``.

    :raises ValueError: When the table has no link_row field or several.
    """

    links = list(LinkRowField.objects.filter(table=table).order_by("id"))
    if len(links) == 1:
        return links[0]
    found = (
        f"has the link_row fields {', '.join(repr(x.name) for x in links)}"
        if links
        else "has no link_row field"
    )
    raise ValueError(
        f"Table '{table.name}' {found}. Set linked_table or through_field for "
        f"lookup '{f.name}'."
    )


def _lookup_link_field(f, table, user) -> LinkRowField | None:
    """The link_row field a lookup goes through, or None when there is none yet."""

    if f.through_field is not None:
        return _named_link_field(f, table, user)
    if f.linked_table is None:
        return _only_link_field(f, table)
    linked = _resolve_linked_table(f.linked_table, table, user)
    return (
        LinkRowField.objects.filter(table=table, link_row_table=linked)
        .order_by("id")
        .first()
    )


def create_missing_link_field(
    f: "FieldItemCreate", table: Table, user
) -> LinkRowField | None:
    """
    Create the link_row field a lookup to ``linked_table`` needs, when the table
    has none to that table yet.

    :returns: The created link_row field, or None when nothing was created.
    """

    if f.type != "lookup" or _lookup_link_field(f, table, user) is not None:
        return None
    linked = _resolve_linked_table(f.linked_table, table, user)
    return CreateFieldActionType.do(
        user, table, "link_row", name=linked.name, link_row_table=linked
    )


def _lookup_to_orm(f, table, user):
    through = _lookup_link_field(f, table, user)
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


def _select_options_from_orm(orm_field: BaserowField) -> list[SelectOption]:
    return [
        SelectOption(id=opt.id, value=opt.value, color=opt.color)
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
        description="(link_row, lookup) ID or name of the linked table. A lookup "
        "may leave it out when its table has exactly one link_row field.",
    )
    # (single_select, multiple_select)
    options: list[SelectOptionCreate] | None = Field(
        None,
        description="(single_select, multiple_select) List of options with colors.",
    )
    # (formula)
    formula: str | None = Field(
        None,
        description="(formula) The formula expression, in Baserow formula syntax.",
    )
    # (lookup)
    through_field: int | str | None = Field(
        None,
        description="(lookup) ID or name of the link_row field to look up through. "
        "Instead of linked_table.",
    )
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

        # A string carries no color, so a reused table never reports one as requested
        if isinstance(data.get("options"), list):
            data["options"] = [
                {"value": opt} if isinstance(opt, str) else opt
                for opt in data["options"]
            ]

        return data

    # Required fields per type: {type: [(attr_name, display_name), ...]}
    _REQUIRED_FIELDS: dict[str, list[tuple[str, str]]] = {
        "link_row": [("linked_table", "linked_table")],
        "single_select": [("options", "options")],
        "multiple_select": [("options", "options")],
        # The link comes from linked_table, through_field, or the table's only
        # link_row field.
        "lookup": [("target_field", "target_field")],
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


def _update_simple(f: "FieldItemUpdate", field: BaserowField) -> dict[str, Any]:
    kwargs = {}
    if f.name is not None:
        kwargs["name"] = f.name
    return kwargs


def _update_long_text(f: "FieldItemUpdate", field: BaserowField) -> dict[str, Any]:
    kwargs = _update_simple(f, field)
    if f.rich_text is not None:
        kwargs["long_text_enable_rich_text"] = f.rich_text
    return kwargs


def _update_number(f: "FieldItemUpdate", field: BaserowField) -> dict[str, Any]:
    kwargs = _update_simple(f, field)
    if f.decimal_places is not None:
        kwargs["number_decimal_places"] = f.decimal_places
    if f.suffix is not None:
        kwargs["number_suffix"] = f.suffix
    return kwargs


def _update_rating(f: "FieldItemUpdate", field: BaserowField) -> dict[str, Any]:
    kwargs = _update_simple(f, field)
    if f.max_value is not None:
        kwargs["max_value"] = f.max_value
    return kwargs


def _update_date(f: "FieldItemUpdate", field: BaserowField) -> dict[str, Any]:
    kwargs = _update_simple(f, field)
    if f.include_time is not None:
        kwargs["date_include_time"] = f.include_time
    return kwargs


def option_value_key(value: str) -> str:
    """Compare option values while ignoring case and outer spaces."""

    return value.strip().casefold()


def _check_option_ids(
    existing_ids: set[int], update: list[SelectOptionUpdate], remove_ids: list[int]
) -> None:
    """
    Reject option ids that do not name exactly one option of the field.

    :param existing_ids: The ids of the field's options.
    :param update: The options to change.
    :param remove_ids: The ids of the options to delete.
    :raises ValueError: If an id is not an option of the field, is changed twice, or
        is both changed and removed.
    """

    update_ids = [option.id for option in update]
    unknown = sorted(set(update_ids + remove_ids) - existing_ids)
    if unknown:
        raise ValueError(
            f"Options {unknown} are not options of this field. Use the option ids "
            "from the table schema."
        )
    repeated = sorted({i for i in update_ids if update_ids.count(i) > 1})
    if repeated:
        raise ValueError(f"Options {repeated} are changed more than once.")
    conflicting = sorted(set(update_ids) & set(remove_ids))
    if conflicting:
        raise ValueError(f"Options {conflicting} cannot be changed and removed.")


def _apply_update(
    option: BaserowSelectOption, change: SelectOptionUpdate | None
) -> dict[str, Any]:
    if change is None:
        return {"id": option.id, "value": option.value, "color": option.color}
    return {
        "id": option.id,
        "value": option.value if change.value is None else change.value,
        "color": change.color or option.color,
    }


def _unused_color(used: set[str], index: int) -> str:
    free = [color for color in _SELECT_COLORS if color not in used]
    return free[0] if free else _SELECT_COLORS[index % len(_SELECT_COLORS)]


def _merge_select_options(
    existing: list[BaserowSelectOption],
    add: list[SelectOptionCreate],
    update: list[SelectOptionUpdate],
    remove_ids: list[int],
) -> list[dict[str, Any]]:
    """
    Build the full option list that core expects: the field's options in their
    current order, with the updates applied and the removed ones left out, followed
    by the added ones.

    :param existing: The field's options in their current order.
    :param add: The options to add. A missing color becomes one not in use.
    :param update: The options to change. A missing value or color stays as stored.
    :param remove_ids: The ids of the options to delete.
    :return: The select_options to pass to UpdateFieldActionType.
    """

    _check_option_ids({option.id for option in existing}, update, remove_ids)
    changes = {option.id: option for option in update}
    kept = [
        _apply_update(option, changes.get(option.id))
        for option in existing
        if option.id not in remove_ids
    ]
    renamed_ids = {
        option.id
        for option in existing
        if option.id in changes and changes[option.id].value not in (None, option.value)
    }

    used_colors = {entry["color"] for entry in kept}
    used_colors.update(option.color for option in add if option.color)
    added = []
    for index, option in enumerate(add):
        color = option.color or _unused_color(used_colors, index)
        used_colors.add(color)
        added.append({"value": option.value, "color": color})

    _check_unique_values(kept, added, renamed_ids)
    return [*kept, *added]


def _describe_option(entry: dict[str, Any], renamed_ids: set[int]) -> str:
    if "id" not in entry:
        return f"the new option '{entry['value']}'"
    if entry["id"] in renamed_ids:
        return f"option {entry['id']} renamed to '{entry['value']}'"
    return f"option {entry['id']} '{entry['value']}'"


def _check_unique_values(
    kept: list[dict[str, Any]],
    added: list[dict[str, Any]],
    renamed_ids: set[int],
    hint: str = "Leave out options that already exist to keep them, or change "
    "them with update_options by id.",
) -> None:
    """
    Reject added or renamed values that repeat another option's value, ignoring
    case and surrounding spaces, because tools pick options by value when they
    write cells.
    Duplicates already in the field are left alone.

    :param kept: The field's remaining options, with the updates applied.
    :param added: The options to add.
    :param renamed_ids: The ids of the kept options whose value changes.
    :param hint: How to fix a clash, added to the error.
    :raises ValueError: If an added or renamed value repeats another option's value.
    """

    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in [*kept, *added]:
        groups.setdefault(option_value_key(entry["value"]), []).append(entry)
    clashes = [
        " and ".join(_describe_option(entry, renamed_ids) for entry in group)
        for group in groups.values()
        if len(group) > 1
        and any("id" not in entry or entry["id"] in renamed_ids for entry in group)
    ]
    if clashes:
        raise ValueError(
            "These options would share a value (case and surrounding spaces are "
            f"ignored): {'; '.join(clashes)}. {hint}"
        )


def _changed_default(field: BaserowField, kept_ids: set[int]) -> dict[str, Any]:
    """
    Drop removed options from the field's default, so undo restores it.

    :param field: The select field being updated.
    :param kept_ids: The ids of the options that remain.
    :return: The default kwarg for UpdateFieldActionType when it changes, else {}.
    """

    field_type = field_type_registry.get_by_model(field)
    default = field_type.get_default_value(field)
    if isinstance(default, list):
        kept_default = [option_id for option_id in default if option_id in kept_ids]
    else:
        kept_default = default if default in kept_ids else None
    if kept_default == default:
        return {}
    return {field_type.get_default_options_field_name(): kept_default}


def _update_select(f: "FieldItemUpdate", field: BaserowField) -> dict[str, Any]:
    kwargs = _update_simple(f, field)
    if f.add_options or f.update_options or f.remove_options:
        select_options = _merge_select_options(
            list(field.select_options.all()),
            f.add_options or [],
            f.update_options or [],
            f.remove_options or [],
        )
        kept_ids = {option["id"] for option in select_options if "id" in option}
        kwargs["select_options"] = select_options
        kwargs.update(_changed_default(field, kept_ids))
    return kwargs


def _update_formula(f: "FieldItemUpdate", field: BaserowField) -> dict[str, Any]:
    kwargs = _update_simple(f, field)
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
    add_options: list[SelectOptionCreate] | None = Field(
        None,
        description="(single_select, multiple_select) New options. Omit color to get "
        "one not in use.",
    )
    update_options: list[SelectOptionUpdate] | None = Field(
        None,
        description="(single_select, multiple_select) Existing options to rename or "
        "recolor, by id.",
    )
    remove_options: list[int] | None = Field(
        None,
        description="(single_select, multiple_select) IDs of options to delete, from "
        "the table schema. They are removed from every row.",
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
        if isinstance(data.get("add_options"), list):
            data["add_options"] = [
                {"value": opt} if isinstance(opt, str) else opt
                for opt in data["add_options"]
            ]
        return data

    def to_update_kwargs(self, field: BaserowField) -> dict[str, Any]:
        """
        Build the kwargs for UpdateFieldActionType.do().

        :param field: The specific field to update, in its current state.
        :return: The kwargs for the properties this update changes.
        """

        field_type = field_type_registry.get_by_model(field).type
        builder = _TO_UPDATE_ORM.get(field_type, _update_simple)
        return builder(self, field)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _formula_error(
    exc: InvalidFormulaFieldError, item: str | int, **details: Any
) -> dict[str, Any]:
    """
    The item error of an invalid formula, with what a client needs to repair it.

    :param exc: The formula error.
    :param item: The field's name, or its ID for an update.
    :param details: More keys the client needs, like the update's index.
    :return: The item error.
    """

    return item_error(
        item,
        ToolError(ToolErrorCode.INVALID_FORMULA, exc.error.rstrip(".") + "."),
        table_id=exc.table.id,
        field_name=exc.field_name,
        formula=exc.formula,
        **details,
    )


def _field_item_error(exc: Exception) -> ToolError:
    """
    Classify one field that failed while the others go on. Call it from the
    ``except`` block, so an unexpected error is logged with its traceback.

    :param exc: The exception the item raised.
    :return: The code and the message for people.
    """

    message = user_error_message(exc)
    if message is not None:
        code = (
            ToolErrorCode.CONFLICT
            if isinstance(exc, conflict_errors())
            else ToolErrorCode.INVALID_INPUT
        )
        return ToolError(code, message)
    return classify_item_error(exc, conflict_errors())


def forget_cached_table_models() -> None:
    """
    Drop the table models cached for this request. Call it after a savepoint
    rolls back, because a model built inside it can still be cached. Every table
    is dropped, as a link field also changes the model of the table it links to.
    """

    local_cache.delete("database_table_model_*")


def _get_field(ctx: ToolContext, field_id: int) -> BaserowField:
    """
    Get a field of a table the user can see in the context's workspace.

    :raises FieldDoesNotExist: When the field is missing, trashed or outside the
        workspace.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    return FieldHandler().get_field(
        field_id, base_queryset=BaserowField.objects.filter(table__in=tables)
    )


def create_fields_in_table(
    ctx: ToolContext, table: Table, field_items: list[FieldItemCreate]
) -> tuple[list[FieldItem], list[dict[str, Any]]]:
    """
    Create fields in a table, in an order that lets later fields refer to earlier
    ones: regular fields first, then link_row, lookup and formula.

    :param ctx: Who acts and where status goes.
    :param table: The table to add the fields to.
    :param field_items: The fields to create.
    :returns: The created fields, and an item error per field that could not be
        created; an invalid formula has the code ``invalid_formula`` and its formula.
    :raises PermissionException: When the user may not create a field.
    """

    created_fields: list[FieldItem] = []
    errors: list[dict[str, Any]] = []

    for field_item in sorted(field_items, key=lambda f: FIELD_ORDER.get(f.type, 0)):
        ctx.update_status(
            _("Creating field %(field_name)s...") % {"field_name": field_item.name}
        )
        try:
            # A savepoint, so a failed field leaves the transaction usable.
            with transaction.atomic():
                link_field = create_missing_link_field(field_item, table, ctx.user)
                new_field = CreateFieldActionType.do(
                    ctx.user,
                    table,
                    field_item.type,
                    **field_item.to_django_orm_kwargs(table, user=ctx.user),
                )
            if link_field is not None:
                created_fields.append(FieldItem.from_django_orm(link_field))
            created_fields.append(FieldItem.from_django_orm(new_field))
        except InvalidFormulaFieldError as exc:
            errors.append(_formula_error(exc, field_item.name))
        except PermissionException:
            raise
        except Exception as error:
            forget_cached_table_models()
            errors.append(
                item_error(field_item.name, _field_item_error(error), table_id=table.id)
            )
    return created_fields, errors


def update_field(
    ctx: ToolContext, field_update: FieldItemUpdate
) -> tuple[FieldItem, bool]:
    """
    Update a field of the context's workspace.

    :param ctx: Who acts.
    :param field_update: The changes to make.
    :returns: The field as it is now, and whether it changed.
    :raises FieldDoesNotExist: When the field is not in the workspace.
    :raises InvalidFormulaFieldError: When the new formula is invalid. Nothing is
        changed then.
    """

    _get_field(ctx, field_update.field_id)
    # Locked like the REST API does, so concurrent option changes don't merge from
    # a stale read.
    field = FieldHandler().get_specific_field_for_update(field_update.field_id)
    kwargs = field_update.to_update_kwargs(field)
    previous = FieldItem.from_django_orm(field)
    if not kwargs:
        return previous, False

    if "formula" in kwargs:
        check_formula(field.table, kwargs.get("name", field.name), kwargs["formula"])

    UpdateFieldActionType.do(ctx.user, field, **kwargs)
    updated_field = FieldHandler().get_field(field_update.field_id).specific
    current = FieldItem.from_django_orm(updated_field)
    return current, current != previous


def delete_field(ctx: ToolContext, field_id: int) -> None:
    """
    Move a field of the context's workspace to the trash.

    :raises FieldDoesNotExist: When the field is not in the workspace.
    """

    DeleteFieldActionType.do(ctx.user, _get_field(ctx, field_id).specific)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def create_fields(
    ctx: ToolContext,
    table_id: Annotated[
        int, Field(description="The ID of the table to add fields to.")
    ],
    fields: Annotated[
        list[FieldItemCreate],
        Field(description="The fields to create, with their types and settings."),
    ],
) -> dict[str, Any]:
    """
    Add fields to a table. Field names must be unique in the table, and the table
    of a link_row or lookup field must already exist. A lookup goes through the
    link_row field named in through_field, or else the first one to linked_table;
    when there is none, one is created and returned in created_fields too. A
    formula is stored as written. An invalid formula is not created: it is
    returned in errors with the code invalid_formula and the parser's message, to
    correct and send again.
    """

    table = (
        TableHandler().list_workspace_tables(ctx.user, ctx.workspace).get(id=table_id)
    )
    with transaction.atomic():
        created, errors = create_fields_in_table(ctx, table, fields)
    return finish_batch(
        {"created_fields": [f.model_dump() for f in created]},
        bool(created),
        errors,
        "No field was created.",
    )


def _fields_to_lock(ctx: ToolContext, field_ids: list[int]):
    """
    The requested fields of the workspace, locked with their table like
    ``FieldHandler.get_specific_field_for_update`` does, in table and field id
    order.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    return (
        BaserowField.objects.filter(id__in=field_ids, table__in=tables)
        .select_related("table")
        .select_for_update(
            of=("self", "table"), nowait=settings.BASEROW_NOWAIT_FOR_LOCKS
        )
        .order_by("table_id", "id")
    )


def _lock_fields(ctx: ToolContext, field_ids: list[int]) -> None:
    """
    Lock every requested field before the first update. Concurrent calls then take
    the locks in one order, which makes a deadlock between them less likely.

    :raises DjangoValidationError: With the REST API's message when another
        operation holds a lock and Baserow doesn't wait for it.
    """

    try:
        list(_fields_to_lock(ctx, field_ids))
    except DatabaseError as exc:
        if "could not obtain lock on row" not in str(exc):
            raise
        raise DjangoValidationError(
            user_error_message(FailedToLockFieldDueToConflict())
        ) from exc


def update_fields(
    ctx: ToolContext,
    fields: Annotated[
        list[FieldItemUpdate],
        Field(
            description="The field updates, each with a field_id and the properties "
            "to change."
        ),
    ],
) -> dict[str, Any]:
    """
    Update fields: rename them or change their settings and select options. A
    field's type and link_row target cannot change. Select options not listed stay
    as they are. A field with an invalid formula is left unchanged and returned in
    errors with the code invalid_formula, the parser's message and the index of its
    update in fields.
    """

    updated = []
    errors: list[dict[str, Any]] = []
    changed = False

    with transaction.atomic():
        _lock_fields(ctx, [field_update.field_id for field_update in fields])
        # Applied in the caller's order, so a rename can come before a formula
        # that uses the new name.
        for index, field_update in enumerate(fields):
            ctx.update_status(
                _("Updating field %(field_id)s...")
                % {"field_id": field_update.field_id}
            )
            try:
                with transaction.atomic():
                    field_item, field_changed = update_field(ctx, field_update)
                updated.append(field_item.model_dump())
                changed = changed or field_changed
            except InvalidFormulaFieldError as exc:
                errors.append(
                    _formula_error(
                        exc,
                        field_update.field_id,
                        field_id=field_update.field_id,
                        index=index,
                    )
                )
            except PermissionException:
                raise
            except Exception as error:
                forget_cached_table_models()
                errors.append(
                    item_error(field_update.field_id, _field_item_error(error))
                )
    return finish_batch(
        {"updated_fields": updated}, changed, errors, "No field was updated."
    )


def delete_fields(
    ctx: ToolContext,
    field_ids: Annotated[
        list[int], Field(description="The IDs of the fields to delete.")
    ],
) -> dict[str, Any]:
    """
    Move fields to the trash, from where they can be restored. A primary field
    cannot be deleted.
    """

    deleted = []
    errors: list[dict[str, Any]] = []

    with transaction.atomic():
        for field_id in field_ids:
            ctx.update_status(
                _("Deleting field %(field_id)s...") % {"field_id": field_id}
            )
            try:
                with transaction.atomic():
                    delete_field(ctx, field_id)
                deleted.append(field_id)
            except PermissionException:
                raise
            except Exception as error:
                forget_cached_table_models()
                errors.append(item_error(field_id, _field_item_error(error)))
    return finish_batch(
        {"deleted_field_ids": deleted}, bool(deleted), errors, "No field was deleted."
    )
