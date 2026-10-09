"""Table element columns as Kuma reads and changes them."""

from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

from pydantic import Field, model_validator

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.database.api.fields.serializers import FileFieldResponseSerializer
from baserow.contrib.database.fields.utils import (
    guess_json_type_from_response_serializer_field,
)
from baserow.core.db import specific_iterator
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.assistant.types import BaseModel

from .changes import NO_CHANGES, name_key

if TYPE_CHECKING:
    from baserow.contrib.builder.elements.models import CollectionField, TableElement
    from baserow.contrib.database.fields.models import Field as DatabaseField
    from baserow.contrib.database.table.models import Table

VALUE_COLUMN_TYPES: frozenset[str] = frozenset({"text", "boolean", "rating"})
COLUMN_NAME_MAX_LENGTH = 225


class TableColumnItem(TypedDict):
    """One table column as the model reads it."""

    uid: str
    name: str
    type: str
    value: NotRequired[str]
    label: NotRequired[str]


class TableColumnAdd(BaseModel):
    """A new table column. Only text and button columns can be added."""

    name: str = Field(
        ...,
        max_length=COLUMN_NAME_MAX_LENGTH,
        description="Column header. It must differ from the other columns' headers.",
    )
    type: Literal["text", "button"] = Field(
        default="text", description="'text' (default) or 'button'."
    )
    value: str | None = Field(
        default=None,
        description="(text) Fixed text or a runtime formula such as get('current_record.field_<id>'); '' leaves the cells empty. Omit value and field_id to show the data source field named like the column.",
    )
    field_id: int | None = Field(
        default=None,
        description="(text) Database field to show, from get_tables_schema.",
    )
    label: str | None = Field(
        default=None,
        description="(button) Button caption. Defaults to name. Attach click actions with create_actions.",
    )
    before_uid: str | None = Field(
        default=None,
        description="Insert before this column (uid from list_elements). Omit to add it last.",
    )


class TableColumnUpdate(BaseModel):
    """A change to one existing table column. Keys you omit keep their current value."""

    uid: str = Field(..., description="The column's uid, from list_elements.")
    name: str | None = Field(
        default=None,
        max_length=COLUMN_NAME_MAX_LENGTH,
        description="New header. Renaming doesn't change what the column shows.",
    )
    type: str | None = Field(
        default=None,
        description="The column's current type, from list_elements. It can't change.",
    )
    value: str | None = Field(
        default=None,
        description="(text, boolean, rating) New fixed text or runtime formula.",
    )
    field_id: int | None = Field(
        default=None,
        description="(text, boolean, rating) Database field to show instead, from get_tables_schema.",
    )
    label: str | None = Field(default=None, description="(button) New button caption.")

    @model_validator(mode="after")
    def _require_a_change(self) -> "TableColumnUpdate":
        changes = (self.name, self.value, self.field_id, self.label)
        if all(change is None for change in changes):
            raise ValueError(
                f"Column {self.uid} needs a new name, value, field_id or label."
            )
        return self


class RemovedTableColumn(TypedDict):
    """A column an update removed."""

    uid: str
    name: str
    type: str
    deleted_click_actions: NotRequired[int]


def stored_formula_text(config: Any, key: str) -> str:
    """
    Read the formula text stored under one key of a column config.

    :param config: The column config. Old rows can hold None or plain strings.
    :param key: "value" or "label".
    :return: The formula text, or "" when there is none.
    """

    raw = config.get(key) if isinstance(config, dict) else None
    if isinstance(raw, dict):
        raw = raw.get("formula")
    return raw if isinstance(raw, str) else ""


def table_column_item(column: "CollectionField") -> TableColumnItem:
    """
    Describe one column as the model reads it.

    :param column: The stored column.
    :return: Its uid, name and type, plus its value or label formula when it has one.
    """

    item = TableColumnItem(uid=str(column.uid), name=column.name, type=column.type)
    if column.type in VALUE_COLUMN_TYPES:
        item["value"] = stored_formula_text(column.config, "value")
    elif column.type == "button":
        item["label"] = stored_formula_text(column.config, "label")
    return item


def table_column_items(element: "TableElement") -> list[TableColumnItem]:
    """
    Describe a table's columns in display order.

    :param element: The table element. Its columns are read from the prefetched
        ones, which CollectionField's ordering keeps in display order, so listing
        many tables runs no query per table.
    :return: One item per column.
    """

    return [table_column_item(column) for column in element.fields.all()]


def data_source_table(data_source_id: int | None) -> "Table | None":
    """
    Find the database table a data source reads.

    :param data_source_id: The data source, or None.
    :return: The table, or None when the data source doesn't exist or is trashed,
        has no service, or its service reads no table.
    """

    if not data_source_id:
        return None
    try:
        data_source = DataSource.objects.select_related("service").get(
            id=data_source_id
        )
    except DataSource.DoesNotExist:
        return None
    if data_source.service is None:
        return None
    return getattr(data_source.service.specific, "table", None)


def table_fields(table: "Table") -> list["DatabaseField"]:
    """
    Read a database table's fields as their specific types, which field_formula
    needs.

    :param table: The database table.
    :return: Its fields that aren't trashed.
    """

    return specific_iterator(table.field_set.select_related("content_type"))


def data_source_fields(data_source_id: int | None) -> dict[str, "DatabaseField"]:
    """
    Read the fields of the database table a data source reads.

    :param data_source_id: The data source, or None.
    :return: Each field as its specific type, by the name_key of its name. Empty when
        there is no data source or it reads no table.
    """

    table = data_source_table(data_source_id)
    if table is None:
        return {}
    return {name_key(field.name): field for field in table_fields(table)}


def field_formula(field: "DatabaseField") -> str:
    """
    Build the runtime formula that shows a database field in a text column.

    The path into the field's value reads the value or name of each item, like the
    table editor's default columns (getDefaultCollectionFields in
    web-frontend/modules/integrations/localBaserow/serviceTypes.js).

    :param field: The database field, as its specific type.
    :return: get('current_record.field_<id><path>').
    :raises ToolInputError: When the field holds files, which a text column can't
        show.
    """

    serializer_field = field.get_type().get_response_serializer_field(field)
    if _holds_files(serializer_field):
        raise ToolInputError(
            f"Field {field.id} '{field.name}' holds files, which a text column can't "
            "show. Show another field, or add an image column in the table's editor. "
            f"{NO_CHANGES}"
        )
    shape = guess_json_type_from_response_serializer_field(serializer_field)
    return f"get('current_record.field_{field.id}{_value_path(shape)}')"


def _holds_files(serializer_field: Any) -> bool:
    item = getattr(serializer_field, "child", serializer_field)
    return isinstance(item, FileFieldResponseSerializer)


def _value_path(shape: dict[str, Any]) -> str:
    if shape.get("type") != "array":
        return _item_path(shape)
    item_path = _item_path(shape.get("items") or {})
    return f".*{item_path}" if item_path else ""


def _item_path(shape: dict[str, Any]) -> str:
    properties = shape.get("properties") or {}
    return next((f".{key}" for key in ("value", "name") if key in properties), "")
