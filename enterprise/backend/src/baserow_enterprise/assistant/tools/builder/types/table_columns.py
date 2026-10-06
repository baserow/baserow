"""Table element columns as Kuma reads and changes them."""

from typing import TYPE_CHECKING, Any, NotRequired, TypedDict

if TYPE_CHECKING:
    from baserow.contrib.builder.elements.models import CollectionField, TableElement

VALUE_COLUMN_TYPES: frozenset[str] = frozenset({"text", "boolean", "rating"})


class TableColumnItem(TypedDict):
    """One table column as the model reads it."""

    uid: str
    name: str
    type: str
    value: NotRequired[str]
    label: NotRequired[str]


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
