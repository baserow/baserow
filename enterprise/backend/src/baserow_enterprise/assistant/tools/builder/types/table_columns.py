"""Table element columns as Kuma reads and changes them."""

from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

from pydantic import Field, model_validator

from baserow.contrib.builder.data_sources.models import DataSource
from baserow_enterprise.assistant.types import BaseModel

if TYPE_CHECKING:
    from baserow.contrib.builder.elements.models import CollectionField, TableElement
    from baserow.contrib.database.table.models import Table

VALUE_COLUMN_TYPES: frozenset[str] = frozenset({"text", "boolean", "rating"})
COLUMN_NAME_MAX_LENGTH = 225

# Mirrors LocalBaserowListRowsUserServiceType.get_default_collection_fields().
FORMULA_PATH_SUFFIX: dict[str, str] = {
    "last_modified_by": ".name",
    "created_by": ".name",
    "single_select": ".value",
    "multiple_collaborators": ".*.name",
}
ARRAY_FIELD_TYPES = {"multiple_select", "link_row"}


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


def column_name_key(name: str) -> str:
    """
    Compare column and field names ignoring case and surrounding spaces.

    :param name: A column or field name.
    :return: The comparison key.
    """

    return name.strip().casefold()


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

    :param element: The table element. Its prefetched columns are sorted here, so
        listing many tables runs no query per table.
    :return: One item per column.
    """

    columns = sorted(element.fields.all(), key=lambda column: (column.order, column.id))
    return [table_column_item(column) for column in columns]


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


def data_source_fields(data_source_id: int | None) -> dict[str, tuple[int, str]]:
    """
    Read the fields of the database table a data source reads.

    :param data_source_id: The data source, or None.
    :return: (field id, field type) by the column_name_key of each field name. Empty
        when there is no data source or it reads no table.
    """

    table = data_source_table(data_source_id)
    if table is None:
        return {}
    return {
        column_name_key(field.name): (field.id, field.get_type().type)
        for field in table.field_set.select_related("content_type")
    }


def field_formula(field_id: int, field_type: str) -> str:
    """
    Build the runtime formula that shows a database field in a column.

    :param field_id: The database field.
    :param field_type: The database field's type.
    :return: get('current_record.field_<id><suffix>'), where the suffix reads the
        names or values of select, link and collaborator fields.
    """

    suffix = FORMULA_PATH_SUFFIX.get(field_type, "")
    if not suffix and field_type in ARRAY_FIELD_TYPES:
        suffix = ".*.value"
    return f"get('current_record.field_{field_id}{suffix}')"
