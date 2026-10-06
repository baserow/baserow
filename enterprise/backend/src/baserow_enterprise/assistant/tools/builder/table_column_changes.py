"""Turn Kuma's table column changes into the full column list core saves."""

import uuid
from collections import Counter
from collections.abc import Iterable
from copy import deepcopy
from typing import Any, NamedTuple, TypeVar

from baserow.contrib.builder.elements.models import TableElement
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.table.models import Table
from baserow.core.formula.types import BASEROW_FORMULA_MODE_ADVANCED
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.assistant.tools.shared.formula_utils import (
    formula_desc,
    formula_object,
    is_valid_formula,
    needs_formula,
    wrap_static_string,
)

from .types.table_columns import (
    NO_CHANGES,
    VALUE_COLUMN_TYPES,
    RemovedTableColumn,
    TableColumnAdd,
    TableColumnUpdate,
    column_name_key,
    data_source_table,
    field_formula,
    stored_formula_text,
    table_fields,
)

MAX_LISTED_COLUMNS = 25

Column = dict[str, Any]

_Item = TypeVar("_Item")

_LABEL_COLUMN_TYPES = frozenset({"button"})
_NEW_VALUE_COLUMN_TYPES = frozenset({"text"})


class TableColumnsChange(NamedTuple):
    """The columns to save for a table, and the stored columns they leave out."""

    fields: list[Column]
    removed: list[RemovedTableColumn]


class SourceTable(NamedTuple):
    """The database table a table element's data source reads, and its fields."""

    table: Table | None
    fields_by_id: dict[int, Field]
    fields_by_name: dict[str, Field]


def column_uid(raw: str) -> str:
    """
    Canonicalize a uid the model sent so it compares equal to stored uids.

    :param raw: The uid as sent.
    :return: The lower-case hyphenated uid, or the stripped input if it isn't a UUID.
    """

    try:
        return str(uuid.UUID(raw.strip()))
    except ValueError:
        return raw.strip()


def column_formula(text: str, column_name: str, key: str) -> str:
    """
    Turn a value or label the model sent into the formula to store.

    :param text: Fixed text or a runtime formula.
    :param column_name: The column's header, for the error message.
    :param key: "value" or "label", for the error message.
    :return: "''" for empty text, a quoted literal for fixed text, or the formula.
    :raises ToolInputError: When the text needs a formula that doesn't parse.
    """

    if text == "":
        return "''"
    if not needs_formula(text):
        return wrap_static_string(text)
    formula = formula_desc(text)
    if not is_valid_formula(formula):
        raise ToolInputError(
            f"Column '{column_name}' has a {key} that is not a valid formula. For "
            "fixed text, put it in single quotes; to show data, set field_id or use a "
            "runtime formula such as get('current_record.field_<id>'). \"$formula:\" "
            f"descriptions are generated only when a table is created. {NO_CHANGES}"
        )
    return formula


def merge_table_columns(
    element: TableElement,
    add: list[TableColumnAdd],
    update: list[TableColumnUpdate],
    reorder: list[str] | None,
    remove: list[str],
) -> TableColumnsChange:
    """
    Merge column changes into the full column list core saves for a table.

    Columns the changes don't name are resent exactly as stored, so they keep their
    uid, settings, styles and click actions. A field_id, or a new text column without
    a value, shows a field of the table the element's data source reads.

    :param element: The table element, locked for update.
    :param add: New columns.
    :param update: Changes to existing columns, by uid.
    :param reorder: The uids of every column that stays in the new order, or None to
        keep the stored order.
    :param remove: The uids of the columns to delete.
    :return: The columns to save and the columns removed.
    :raises ToolInputError: When a change can't be applied; nothing is saved.
    """

    stored = _stored_columns(element)
    by_uid = {column["uid"]: column for column in stored}
    update_uids = [column_uid(change.uid) for change in update]
    remove_uids = [column_uid(uid) for uid in remove]
    order = [column_uid(uid) for uid in reorder] if reorder is not None else None
    anchors = [column_uid(new.before_uid) for new in add if new.before_uid is not None]

    _check_references(
        element, stored, [*update_uids, *remove_uids, *(order or []), *anchors]
    )
    removed_uids = set(remove_uids)
    _check_changed_once(update_uids, removed_uids)
    _check_types_fit(update, update_uids, add, by_uid)
    _check_value_or_field_id(update, update_uids, add, by_uid)

    kept = [column for column in stored if column["uid"] not in removed_uids]
    removed = [column for column in stored if column["uid"] in removed_uids]
    if order is not None:
        _check_order(kept, order, removed_uids, by_uid)
        position = {uid: index for index, uid in enumerate(order)}
        kept.sort(key=lambda column: position[column["uid"]])
    _check_anchors_stay(anchors, removed_uids)
    _check_not_added_again(add, removed)
    changes = dict(zip(update_uids, update))
    _check_names(_merged_names(kept, changes, add), stored)

    binds_a_field = _binds_a_field(add, update)
    if binds_a_field:
        _check_rows_are_records(element)
    source = (
        _source_table(element.data_source_id)
        if binds_a_field
        else SourceTable(None, {}, {})
    )
    _check_field_ids(element, source, update, add)
    _check_new_columns_not_empty(element, source, add)

    merged = [_changed(column, changes.get(column["uid"]), source) for column in kept]
    for new in add:
        merged.insert(_insert_index(merged, new.before_uid), _new_column(new, source))

    if not merged:
        raise ToolInputError(
            f"Table element {element.id} would have no columns left. Keep a column, or "
            f"add one with add_table_columns in the same call. {NO_CHANGES}"
        )
    if merged == stored:
        raise ToolInputError(
            f"No column of table element {element.id} would change: the names, "
            "values, field ids and labels you sent are already stored, and the order "
            "is the same. Columns you don't list stay as they are; to move columns, "
            f"use reorder_table_columns. {NO_CHANGES}"
        )
    return TableColumnsChange(merged, _removed_items(element, removed))


def _stored_columns(element: TableElement) -> list[Column]:
    return [
        {
            "uid": str(column.uid),
            "name": column.name,
            "type": column.type,
            "config": column.config,
            "styles": column.styles,
        }
        for column in element.fields.all()
    ]


def _unique(items: Iterable[_Item]) -> list[_Item]:
    return list(dict.fromkeys(items))


def _listing(columns: list[Column]) -> str:
    listed = ", ".join(
        f"{column['uid']} '{column['name']}' ({column['type']})"
        for column in columns[:MAX_LISTED_COLUMNS]
    )
    hidden = len(columns) - MAX_LISTED_COLUMNS
    return f"{listed}, and {hidden} more (see list_elements)" if hidden > 0 else listed


def _named(uids: list[str], by_uid: dict[str, Column]) -> str:
    return ", ".join(f"{uid} '{by_uid[uid]['name']}'" for uid in uids)


def _check_references(
    element: TableElement, stored: list[Column], uids: list[str]
) -> None:
    counts = Counter(column["uid"] for column in stored)
    unknown = _unique(uid for uid in uids if uid not in counts)
    if unknown:
        raise ToolInputError(
            f"Columns {unknown} are not columns of table element {element.id}. Its "
            f"columns are: {_listing(stored)}. Use these uids. {NO_CHANGES}"
        )
    shared = _unique(uid for uid in uids if counts[uid] > 1)
    if shared:
        raise ToolInputError(
            f"Columns {shared} of table element {element.id} share a uid with another "
            "column, so they can't be told apart. Remove one of them in the table's "
            f"editor, then retry. {NO_CHANGES}"
        )


def _check_changed_once(update_uids: list[str], removed_uids: set[str]) -> None:
    repeated = [uid for uid, count in Counter(update_uids).items() if count > 1]
    if repeated:
        raise ToolInputError(
            f"Columns {repeated} are changed more than once. Put all changes to a "
            f"column in one update_table_columns entry. {NO_CHANGES}"
        )
    both = _unique(uid for uid in update_uids if uid in removed_uids)
    if both:
        raise ToolInputError(
            f"Columns {both} cannot be changed and removed. {NO_CHANGES}"
        )


def _misfit_keys(
    entry: TableColumnAdd | TableColumnUpdate,
    column_type: str,
    value_types: frozenset[str],
) -> list[str]:
    fitting_types = {
        "value": value_types,
        "field_id": value_types,
        "label": _LABEL_COLUMN_TYPES,
    }
    return [
        key
        for key, types in fitting_types.items()
        if getattr(entry, key) is not None and column_type not in types
    ]


def _check_types_fit(
    update: list[TableColumnUpdate],
    update_uids: list[str],
    add: list[TableColumnAdd],
    by_uid: dict[str, Column],
) -> None:
    retyped = [
        f"Column {uid} '{by_uid[uid]['name']}' is a {by_uid[uid]['type']} column, and "
        "a column's type can't change."
        for change, uid in zip(update, update_uids)
        if change.type is not None
        and change.type.strip().casefold() != by_uid[uid]["type"]
    ]
    if retyped:
        raise ToolInputError(
            f"{' '.join(retyped)} Only remove it and add a new column of another type "
            "if the user asked for that: its settings and click actions are lost. "
            f"{NO_CHANGES}"
        )
    misfits = [
        f"column {uid} '{by_uid[uid]['name']}' is a {by_uid[uid]['type']} column, "
        f"so {key} does not apply"
        for change, uid in zip(update, update_uids)
        for key in _misfit_keys(change, by_uid[uid]["type"], VALUE_COLUMN_TYPES)
    ]
    misfits += [
        f"the new column '{new.name}' is a {new.type} column, so {key} does not apply"
        for new in add
        for key in _misfit_keys(new, new.type, _NEW_VALUE_COLUMN_TYPES)
    ]
    if misfits:
        raise ToolInputError(
            f"These changes don't fit the column type: {'; '.join(misfits)}. value and "
            "field_id are for text, boolean and rating columns, and label for button "
            "columns; link, tags and image columns can only be renamed or reordered "
            "here; their other settings are changed in the table's editor. "
            f"{NO_CHANGES}"
        )


def _check_value_or_field_id(
    update: list[TableColumnUpdate],
    update_uids: list[str],
    add: list[TableColumnAdd],
    by_uid: dict[str, Column],
) -> None:
    refs = [
        f"Column {uid} '{by_uid[uid]['name']}'"
        for change, uid in zip(update, update_uids)
        if change.value is not None and change.field_id is not None
    ]
    refs += [
        f"The new column '{new.name}'"
        for new in add
        if new.value is not None and new.field_id is not None
    ]
    if refs:
        both = " ".join(f"{ref} has both value and field_id." for ref in refs)
        raise ToolInputError(f"{both} Set only one. {NO_CHANGES}")


def _check_order(
    kept: list[Column],
    order: list[str],
    removed_uids: set[str],
    by_uid: dict[str, Column],
) -> None:
    listed = Counter(order)
    problems = {
        "Missing": [column["uid"] for column in kept if column["uid"] not in listed],
        "Listed more than once": [uid for uid, count in listed.items() if count > 1],
        "Removed in this call": [uid for uid in listed if uid in removed_uids],
    }
    details = "".join(
        f" {problem}: {_named(uids, by_uid)}."
        for problem, uids in problems.items()
        if uids
    )
    if details:
        raise ToolInputError(
            "reorder_table_columns must list every column that stays exactly once."
            f"{details} {NO_CHANGES}"
        )


def _check_anchors_stay(anchors: list[str], removed_uids: set[str]) -> None:
    removed_anchors = _unique(uid for uid in anchors if uid in removed_uids)
    if removed_anchors:
        raise ToolInputError(
            f"Columns {removed_anchors} are removed in this call, so new columns "
            f"can't be placed before them. {NO_CHANGES}"
        )


def _bound_by_name(new: TableColumnAdd) -> bool:
    return new.type == "text" and new.value is None and new.field_id is None


def _binds_a_field(add: list[TableColumnAdd], update: list[TableColumnUpdate]) -> bool:
    return any(entry.field_id is not None for entry in [*update, *add]) or any(
        _bound_by_name(new) for new in add
    )


def _check_rows_are_records(element: TableElement) -> None:
    if element.schema_property:
        raise ToolInputError(
            f"Table element {element.id} lists the items of its data source's "
            f"'{element.schema_property}' property, so columns can't be bound to "
            f"database fields. Set value instead. {NO_CHANGES}"
        )


def _source_table(data_source_id: int | None) -> SourceTable:
    table = data_source_table(data_source_id)
    fields = table_fields(table) if table else []
    return SourceTable(
        table,
        {field.id: field for field in fields},
        {column_name_key(field.name): field for field in fields},
    )


def _check_field_ids(
    element: TableElement,
    source: SourceTable,
    update: list[TableColumnUpdate],
    add: list[TableColumnAdd],
) -> None:
    field_ids = _unique(
        entry.field_id for entry in [*update, *add] if entry.field_id is not None
    )
    if not field_ids:
        return
    if source.table is None:
        raise ToolInputError(
            f"Table element {element.id} has no data source with a database table, so "
            f"field_id can't be used. Set value instead. {NO_CHANGES}"
        )
    unknown = [
        field_id for field_id in field_ids if field_id not in source.fields_by_id
    ]
    if unknown:
        raise ToolInputError(
            f"Fields {unknown} are not fields of table {source.table.id} "
            f"'{source.table.name}', which the data source of table element "
            f"{element.id} reads. Use field ids of that table from get_tables_schema. "
            f"{NO_CHANGES}"
        )


def _check_new_columns_not_empty(
    element: TableElement, source: SourceTable, add: list[TableColumnAdd]
) -> None:
    names = [new.name for new in add if _bound_by_name(new)]
    if source.table is None:
        empty = [
            f"The new column '{name}' would be empty because table element "
            f"{element.id} has no data source with a database table."
            for name in names
        ]
        remedy = "Set value."
    else:
        empty = [
            f"The new column '{name}' would be empty: table {source.table.id} "
            f"'{source.table.name}' has no field named '{name}'."
            for name in names
            if column_name_key(name) not in source.fields_by_name
        ]
        remedy = (
            "Set field_id (from get_tables_schema) or value; value '' keeps it empty "
            "on purpose."
        )
    if empty:
        raise ToolInputError(f"{' '.join(empty)} {remedy} {NO_CHANGES}")


def _new_name(column: Column, change: TableColumnUpdate | None) -> str:
    return column["name"] if change is None or change.name is None else change.name


def _changed(
    column: Column, change: TableColumnUpdate | None, source: SourceTable
) -> Column:
    if change is None:
        return column
    config = deepcopy(column["config"]) if isinstance(column["config"], dict) else {}
    sent = {"value": change.value, "label": change.label}
    if change.field_id is not None:
        sent["value"] = field_formula(source.fields_by_id[change.field_id])
    for key, text in sent.items():
        stored_text = stored_formula_text(column["config"], key).strip()
        if text is None or text.strip() == stored_text:
            continue
        formula = column_formula(text, column["name"], key)
        if formula.strip() != stored_text:
            config[key] = formula_object(formula, mode=BASEROW_FORMULA_MODE_ADVANCED)
    return {**column, "name": _new_name(column, change), "config": config}


def _insert_index(merged: list[Column], before_uid: str | None) -> int:
    if before_uid is None:
        return len(merged)
    anchor = column_uid(before_uid)
    return next(
        index for index, column in enumerate(merged) if column.get("uid") == anchor
    )


def _new_value(new: TableColumnAdd, source: SourceTable) -> str:
    if new.value is not None:
        return new.value
    if new.field_id is not None:
        return field_formula(source.fields_by_id[new.field_id])
    return field_formula(source.fields_by_name[column_name_key(new.name)])


def _new_column(new: TableColumnAdd, source: SourceTable) -> Column:
    if new.type == "button":
        key, text = "label", new.label or new.name
    else:
        key, text = "value", _new_value(new, source)
    formula = column_formula(text, new.name, key)
    return {
        "name": new.name,
        "type": new.type,
        "config": {key: formula_object(formula, mode=BASEROW_FORMULA_MODE_ADVANCED)},
    }


def _is_new_or_renamed(column: Column, stored_names: set[tuple[str, str]]) -> bool:
    return "uid" not in column or (column["uid"], column["name"]) not in stored_names


def _name_owner(column: Column, stored_names: set[tuple[str, str]]) -> str:
    if "uid" not in column:
        return f"the new column '{column['name']}'"
    if (column["uid"], column["name"]) not in stored_names:
        return f"column {column['uid']} renamed to '{column['name']}'"
    return f"column {column['uid']} '{column['name']}'"


def _merged_names(
    kept: list[Column],
    changes: dict[str, TableColumnUpdate],
    add: list[TableColumnAdd],
) -> list[Column]:
    columns = [
        {"uid": column["uid"], "name": _new_name(column, changes.get(column["uid"]))}
        for column in kept
    ]
    for new in add:
        columns.insert(_insert_index(columns, new.before_uid), {"name": new.name})
    return columns


def _check_names(columns: list[Column], stored: list[Column]) -> None:
    stored_names = {(column["uid"], column["name"]) for column in stored}
    groups: dict[str, list[Column]] = {}
    for column in columns:
        if key := column_name_key(column["name"]):
            groups.setdefault(key, []).append(column)
    clashes = [
        " and ".join(_name_owner(column, stored_names) for column in group)
        for group in groups.values()
        if len(group) > 1
        and any(_is_new_or_renamed(column, stored_names) for column in group)
    ]
    if clashes:
        raise ToolInputError(
            "These columns would share a name (case and surrounding spaces are "
            f"ignored): {'; '.join(clashes)}. Leave out columns that already exist to "
            "keep them, or change them with update_table_columns by uid. "
            f"{NO_CHANGES}"
        )


def _check_not_added_again(add: list[TableColumnAdd], removed: list[Column]) -> None:
    removed_by_name = {
        (column_name_key(column["name"]), column["type"]): column
        for column in removed
        if column_name_key(column["name"])
    }
    for new in add:
        column = removed_by_name.get((column_name_key(new.name), new.type))
        if column is not None:
            raise ToolInputError(
                f"Column {column['uid']} '{column['name']}' is removed and added "
                "again, which would give it a new uid and drop its styles and click "
                "actions. To move it, use reorder_table_columns; to change it, use "
                f"update_table_columns. {NO_CHANGES}"
            )


def _removed_items(
    element: TableElement, removed: list[Column]
) -> list[RemovedTableColumn]:
    items = []
    for column in removed:
        item = RemovedTableColumn(
            uid=column["uid"], name=column["name"], type=column["type"]
        )
        if column["type"] == "button":
            item["deleted_click_actions"] = BuilderWorkflowAction.objects.filter(
                element=element, event=f"{column['uid']}_click"
            ).count()
        items.append(item)
    return items
