"""
Dynamic Pydantic models for table row CRUD.

Builds per-table create and update models whose fields mirror the table's
database columns, with converters to/from Django ORM representations.
"""

from dataclasses import dataclass
from typing import Any, Callable, Literal, Type

from django.core.exceptions import ValidationError
from django.db.models import Q

from pydantic import ConfigDict, Field, create_model

from baserow.contrib.database.fields.field_types import LinkRowFieldType
from baserow.contrib.database.fields.models import SelectOption as OrmSelectOption
from baserow.contrib.database.table.models import (
    FieldObject,
    GeneratedTableModel,
    Table,
)
from baserow_enterprise.assistant.types import BaseModel

from .base import format_date, format_datetime, parse_date, parse_datetime


@dataclass
class FieldDefinition:
    """
    Pydantic field specification for a single table column.

    When ``type`` is None the field is unsupported and will be skipped
    during model construction.
    """

    type: Type | None = None
    field_def: Any | None = None
    to_django_orm: Callable[[Any], Any] | None = None
    from_django_orm: Callable[[Any], Any] | None = None


# ---------------------------------------------------------------------------
# Per-type builder functions
# ---------------------------------------------------------------------------

# Shared converters for text-like fields
_none_to_empty = lambda v: v if v is not None else ""  # noqa: E731


def _text_field_def(orm_field, orm_field_type):
    return FieldDefinition(
        str | None,
        Field(..., description="Single-line text", title=orm_field.name),
        _none_to_empty,
        _none_to_empty,
    )


def _long_text_field_def(orm_field, orm_field_type):
    return FieldDefinition(
        str | None,
        Field(..., description="Multi-line text", title=orm_field.name),
        _none_to_empty,
        _none_to_empty,
    )


def _number_field_def(orm_field, orm_field_type):
    return FieldDefinition(
        float | None,
        Field(..., description="Number or None", title=orm_field.name),
    )


def _boolean_field_def(orm_field, orm_field_type):
    return FieldDefinition(
        bool, Field(..., description="Boolean", title=orm_field.name)
    )


def _date_field_def(orm_field, orm_field_type):
    if orm_field.date_include_time:
        return FieldDefinition(
            str | None,
            Field(
                ...,
                description="ISO datetime (YYYY-MM-DDTHH:MM) or None",
                title=orm_field.name,
            ),
            lambda v: parse_datetime(v).isoformat() if v else None,
            lambda v: format_datetime(v) if v is not None else None,
        )
    return FieldDefinition(
        str | None,
        Field(..., description="ISO date (YYYY-MM-DD) or None", title=orm_field.name),
        lambda v: parse_date(v).isoformat() if v else None,
        lambda v: format_date(v) if v is not None else None,
    )


def _single_select_field_def(orm_field, orm_field_type):
    choices = [option.value for option in orm_field.select_options.all()]
    if not choices:
        return FieldDefinition()  # Unsupported: no options defined

    return FieldDefinition(
        Literal[*choices] | None,
        Field(
            ...,
            description=f"One of: {', '.join(choices)} or None",
            title=orm_field.name,
        ),
        lambda v: v if v in choices else None,
        lambda v: v.value if isinstance(v, OrmSelectOption) else v,
    )


def _multiple_select_field_def(orm_field, orm_field_type):
    choices = [option.value for option in orm_field.select_options.all()]
    if not choices:
        return FieldDefinition()  # Unsupported: no options defined

    return FieldDefinition(
        list[Literal[*choices]],
        Field(
            ...,
            description=f"List of any of: {', '.join(choices)} or empty list",
            title=orm_field.name,
        ),
        lambda v: [opt for opt in v if opt in choices],
        lambda v: [opt.value for opt in v.all()] if v is not None else [],
    )


def _link_row_field_def(orm_field, orm_field_type):
    linked_model = orm_field.link_row_table.get_model()
    linked_primary_key = linked_model.get_primary_field()
    if linked_primary_key is None:
        return FieldDefinition()

    linked_pk = linked_primary_key.db_column
    examples = list(
        linked_model.objects.exclude(
            Q(**{f"{linked_pk}__isnull": True}) | Q(**{f"{linked_pk}__exact": ""})
        ).values_list("id", linked_pk)[:10]
    )

    def to_django_orm(value):
        if isinstance(value, (str, int)):
            value = [value]
        if value is not None:
            try:
                return LinkRowFieldType().prepare_value_for_db(orm_field, value)
            except ValidationError:
                pass
        return []

    def from_django_orm(value):
        values = [str(v) for v in value.all()]
        if orm_field.link_row_multiple_relationships:
            return values
        return values[0] if values else None

    if orm_field.link_row_multiple_relationships:
        desc = "List of values (as strings) or IDs (as integers) from the linked table or empty list."
        field_type = list[str | int] | None
    else:
        desc = "Single value (as string) or ID (as integer) from the linked table."
        field_type = str | int | None
    if examples:
        desc += (
            " Examples: "
            + ", ".join(f"{{id:{v[0]}, value: `{v[1]}`}}" for v in examples)
            + ", .."
        )
    return FieldDefinition(
        field_type,
        Field(..., description=desc, title=orm_field.name),
        to_django_orm,
        from_django_orm,
    )


_FIELD_DEF_BUILDERS: dict[str, Callable] = {
    "text": _text_field_def,
    "long_text": _long_text_field_def,
    "number": _number_field_def,
    "boolean": _boolean_field_def,
    "date": _date_field_def,
    "single_select": _single_select_field_def,
    "multiple_select": _multiple_select_field_def,
    "link_row": _link_row_field_def,
}


def get_field_definition(field_object: FieldObject) -> FieldDefinition:
    """
    Return a :class:`FieldDefinition` for a table field, or an empty
    (unsupported) definition if the field type has no registered builder.
    """

    orm_field_type = field_object["type"]
    builder = _FIELD_DEF_BUILDERS.get(orm_field_type.type)
    if builder is None:
        return FieldDefinition()
    return builder(field_object["field"], orm_field_type)


# ---------------------------------------------------------------------------
# Helpers shared by create / update models
# ---------------------------------------------------------------------------

# field_conversions maps field names to (db_column, to_orm, from_orm) tuples.
FieldConversions = dict[str, tuple[str, Callable | None, Callable | None]]


def _scan_table_fields(
    table: Table, field_ids: list[int] | None = None
) -> tuple[dict[str, tuple], FieldConversions]:
    """
    Scan a table's fields and return Pydantic field specs plus ORM converters.

    :param table: The table to scan.
    :param field_ids: If given, only include fields with these IDs.
    :returns: ``(field_definitions, field_conversions)`` dicts keyed by field name.
    """

    field_definitions: dict[str, tuple] = {}
    field_conversions: FieldConversions = {}

    for field_object in table.get_model().get_field_objects():
        fd = get_field_definition(field_object)
        if fd.type is None:
            continue
        if field_ids is not None and field_object["field"].id not in field_ids:
            continue

        field = field_object["field"]
        field_definitions[field.name] = (fd.type, fd.field_def)
        field_conversions[field.name] = (
            field.db_column,
            fd.to_django_orm,
            fd.from_django_orm,
        )

    return field_definitions, field_conversions


def _convert_fields(
    items: dict[str, Any], field_conversions: FieldConversions
) -> dict[str, Any]:
    """Convert a {field_name: value} mapping to {db_column: orm_value}."""

    orm_data: dict[str, Any] = {}
    for key, value in items.items():
        if key == "id":
            orm_data["id"] = value
            continue
        if key not in field_conversions:
            continue
        orm_key, converter, _ = field_conversions[key]
        orm_data[orm_key] = converter(value) if converter else value
    return orm_data


# ---------------------------------------------------------------------------
# Row models
# ---------------------------------------------------------------------------


def get_create_row_model(
    table: Table, field_ids: list[int] | None = None
) -> type[BaseModel]:
    """
    Build a Pydantic model for creating rows in the given table.

    The returned model has a field for each supported column, with
    ``to_django_orm()`` and ``from_django_orm()`` for ORM conversion.

    :param table: The table whose columns define the model fields.
    :param field_ids: If given, only include these field IDs.
    """

    field_definitions, field_conversions = _scan_table_fields(table, field_ids)

    class CreateRowModel(BaseModel):
        model_config = ConfigDict(extra="forbid")

        def to_django_orm(self) -> dict[str, Any]:
            return _convert_fields(self.__dict__, field_conversions)

        @classmethod
        def from_django_orm(
            cls, orm_row: GeneratedTableModel, field_ids: list[int] | None = None
        ) -> "CreateRowModel":
            init_data = {}
            if "id" in cls.model_fields:
                init_data["id"] = orm_row.id
            for field_object in orm_row.get_field_objects():
                field = field_object["field"]
                if field.name not in field_conversions:
                    continue
                if field_ids is not None and field.id not in field_ids:
                    continue
                db_column, _, from_django_orm = field_conversions[field.name]
                value = getattr(orm_row, db_column)
                init_data[field.name] = (
                    from_django_orm(value) if from_django_orm else value
                )
            return cls(**init_data)

    return create_model(
        f"Table{table.id}Row",
        __module__=__name__,
        __base__=CreateRowModel,
        **field_definitions,
    )


def get_update_row_model(table: Table) -> type[BaseModel]:
    """
    Build a Pydantic model for updating rows in the given table.

    All fields are optional with ``default=None``; only fields explicitly
    provided during construction are included in ``to_django_orm()`` output,
    so omitting a field means "don't change".

    :param table: The table whose columns define the model fields.
    """

    create_model_class = get_create_row_model(table)
    _, field_conversions = _scan_table_fields(table)

    # All fields become Optional with default=None
    update_fields = {
        name: (
            info.annotation | None,
            Field(default=None, description=info.description, title=info.title),
        )
        for name, info in create_model_class.model_fields.items()
    }
    update_fields["id"] = (int, Field(..., description="The ID of the row to update"))

    class UpdateRowModel(BaseModel):
        model_config = ConfigDict(extra="forbid")

        def to_django_orm(self) -> dict[str, Any]:
            # Only convert explicitly provided fields (pydantic tracks this)
            explicitly_set = {
                k: getattr(self, k) for k in self.model_fields_set if k != "id"
            }
            orm_data = _convert_fields(explicitly_set, field_conversions)
            orm_data["id"] = self.id
            return orm_data

    return create_model(
        f"UpdateTable{table.id}Row",
        __module__=__name__,
        __base__=UpdateRowModel,
        **update_fields,
    )


def get_link_row_hints(row_model: type[BaseModel]) -> str:
    """
    Collect link_row example hints from a row model's field descriptions.

    Returns a formatted string for inclusion in tool descriptions, or an
    empty string if no link_row fields with examples are found.

    :param row_model: A row model built by :func:`get_create_row_model`.
    """

    hints: list[str] = []
    for name, info in row_model.model_fields.items():
        desc = info.description or ""
        if "linked table" in desc and "Examples:" in desc:
            hints.append(f"{name} ({info.title}): {desc}")

    if not hints:
        return ""
    return " LINK_ROW fields: " + "; ".join(hints) + "."
