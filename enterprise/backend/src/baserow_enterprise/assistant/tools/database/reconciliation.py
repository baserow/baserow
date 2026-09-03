from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from baserow.contrib.database.table.models import Table

from .types import FieldItem, FieldItemCreate, TableItem, TableItemCreate

_FIELD_SETTINGS = {
    "long_text": ("rich_text",),
    "number": ("decimal_places", "suffix"),
    "rating": ("max_value",),
    "date": ("include_time",),
    "formula": ("formula",),
}


@dataclass(frozen=True)
class TableCreationPlan:
    """Canonical table requests and their exact-name matches."""

    requested: list[TableItemCreate]
    to_create: list[TableItemCreate]
    to_reuse: list[Table]
    conflicting_names: list[str]


def _canonical_table_requests(
    requested: Sequence[TableItemCreate],
) -> tuple[list[TableItemCreate], list[str]]:
    canonical: list[TableItemCreate] = []
    by_name: dict[str, TableItemCreate] = {}
    conflicting_names: list[str] = []

    for table in requested:
        first_request = by_name.get(table.name)
        if first_request is None:
            canonical.append(table)
            by_name[table.name] = table
        elif table != first_request and table.name not in conflicting_names:
            conflicting_names.append(table.name)

    return canonical, conflicting_names


def plan_table_creation(
    requested: Sequence[TableItemCreate], existing: Iterable[Table]
) -> TableCreationPlan:
    """
    Match requested tables to exact-name tables.

    :param requested: The requested table definitions.
    :param existing: The tables already present in the database.
    :return: The canonical requests split into tables to create and reuse.
    """

    canonical, conflicting_names = _canonical_table_requests(requested)
    existing_by_name = {table.name: table for table in existing}
    to_create: list[TableItemCreate] = []
    to_reuse: list[Table] = []

    for table in canonical:
        existing_table = existing_by_name.get(table.name)
        if existing_table is not None:
            to_reuse.append(existing_table)
            continue

        to_create.append(table)

    return TableCreationPlan(
        requested=canonical,
        to_create=to_create,
        to_reuse=to_reuse,
        conflicting_names=conflicting_names,
    )


def _select_option_conflicts(
    requested: FieldItemCreate, actual: FieldItem
) -> dict[str, Any]:
    actual_by_value = {option.value: option for option in actual.options or []}
    missing = [
        option.model_dump()
        for option in requested.options or []
        if option.value not in actual_by_value
    ]
    wrong_colors = [
        {
            "value": option.value,
            "actual_color": actual_by_value[option.value].color,
            "requested_color": option.color,
        }
        for option in requested.options or []
        if option.value in actual_by_value
        and option.color is not None
        and actual_by_value[option.value].color != option.color
    ]
    conflicts: dict[str, Any] = {}
    if missing:
        conflicts["missing_options"] = missing
    if wrong_colors:
        conflicts["option_color_mismatches"] = wrong_colors
    return conflicts


def _setting_conflicts(requested: FieldItemCreate, actual: FieldItem) -> dict[str, Any]:
    conflicts = {}
    for setting in _FIELD_SETTINGS.get(requested.type, ()):
        requested_value = getattr(requested, setting)
        actual_value = getattr(actual, setting)
        if requested_value != actual_value:
            conflicts[setting] = {
                "actual": actual_value,
                "requested": requested_value,
            }
    return conflicts


def _relation_conflicts(
    requested: FieldItemCreate,
    actual: FieldItem,
    fields_by_id: dict[int, FieldItem],
    table_ids: dict[str, int],
) -> dict[str, Any]:
    requested_table_id = (
        table_ids.get(requested.linked_table)
        if isinstance(requested.linked_table, str)
        else requested.linked_table
    )
    if requested.type == "link_row" and requested_table_id is not None:
        if requested_table_id == actual.linked_table:
            return {}
        return {
            "linked_table": {
                "actual": actual.linked_table,
                "requested": requested_table_id,
            }
        }
    if requested.type == "link_row":
        return {
            "linked_table": {
                "requested": requested.linked_table,
                "actual_id": actual.linked_table,
            }
        }
    if requested.type != "lookup":
        return {}

    through_field = fields_by_id.get(actual.through_field or -1)
    actual_table_id = through_field.linked_table if through_field else None
    conflicts: dict[str, Any] = {}
    if requested_table_id is None or requested_table_id != actual_table_id:
        conflicts["linked_table"] = {
            "actual": actual_table_id,
            "requested": requested.linked_table,
        }
    actual_target = (
        actual.target_field
        if isinstance(requested.target_field, int)
        else actual.target_field_name
    )
    if requested.target_field != actual_target:
        conflicts["target_field"] = {
            "actual": actual_target,
            "requested": requested.target_field,
        }
    return conflicts


def _field_conflict(
    requested: FieldItemCreate,
    actual: FieldItem,
    fields_by_id: dict[int, FieldItem],
    table_ids: dict[str, int],
) -> dict[str, Any] | None:
    field = {"field_id": actual.id, "name": actual.name}
    if actual.type != requested.type:
        return {
            **field,
            "actual_type": actual.type,
            "requested_type": requested.type,
        }

    conflicts: dict[str, Any] = {}
    if requested.type in {"single_select", "multiple_select"}:
        conflicts.update(_select_option_conflicts(requested, actual))
    conflicts.update(_setting_conflicts(requested, actual))
    relation_conflicts = _relation_conflicts(requested, actual, fields_by_id, table_ids)
    if relation_conflicts:
        conflicts["relation_issues"] = relation_conflicts
    return {**field, **conflicts} if conflicts else None


def _primary_field_conflict(
    requested: TableItemCreate, actual: TableItem
) -> dict[str, Any] | None:
    conflict: dict[str, Any] = {"field_id": actual.primary_field.id}
    if actual.primary_field.name != requested.primary_field_name:
        conflict.update(
            actual_name=actual.primary_field.name,
            requested_name=requested.primary_field_name,
        )
    if actual.primary_field.type != "text":
        conflict.update(actual_type=actual.primary_field.type, requested_type="text")
    return conflict if len(conflict) > 1 else None


def table_schema_conflict(
    requested: TableItemCreate,
    actual: TableItem,
    table_ids: dict[str, int] | None = None,
) -> dict[str, Any] | None:
    """
    Describe the requested schema missing from a reused table.

    :param requested: The requested table definition.
    :param actual: The actual schema of the reused table.
    :param table_ids: Mapping of requested table names to created table IDs,
        used to resolve link and lookup targets.
    :return: The conflict description, or None when the table satisfies the
        request.
    """

    primary_conflict = _primary_field_conflict(requested, actual)

    actual_fields = {field.name: field for field in actual.fields}
    fields_by_id = {field.id: field for field in actual.fields}
    missing_fields: list[dict[str, Any]] = []
    field_conflicts: list[dict[str, Any]] = []
    for requested_field in requested.fields:
        if requested_field.name.lower() == requested.primary_field_name.lower():
            continue

        actual_field = actual_fields.get(requested_field.name)
        if actual_field is None:
            missing_fields.append(requested_field.model_dump(exclude_none=True))
            continue

        if field_conflict := _field_conflict(
            requested_field,
            actual_field,
            fields_by_id,
            table_ids or {},
        ):
            field_conflicts.append(field_conflict)

    if not primary_conflict and not missing_fields and not field_conflicts:
        return None

    conflict: dict[str, Any] = {"id": actual.id, "name": actual.name}
    if primary_conflict:
        conflict["primary_field_mismatch"] = primary_conflict
    if missing_fields:
        conflict["missing_fields"] = missing_fields
    if field_conflicts:
        conflict["field_mismatches"] = field_conflicts
    return conflict


def _missing_field_names(conflicts: Sequence[dict[str, Any]]) -> list[str]:
    return [
        field["name"]
        for table in conflicts
        for field in table.get("missing_fields", [])
    ]


def _table_schema_conflicts(
    requested: dict[str, TableItemCreate],
    actual: Sequence[TableItem],
    table_ids: dict[str, int],
) -> list[dict[str, Any]]:
    conflicts = []
    for table in actual:
        conflict = table_schema_conflict(requested[table.name], table, table_ids)
        if conflict is not None:
            conflicts.append(conflict)
    return conflicts


def reused_table_report(
    requested: Sequence[TableItemCreate],
    actual: Sequence[TableItem],
    table_ids: dict[str, int],
) -> dict[str, Any]:
    """
    Build follow-up guidance for incomplete reused tables.

    :param requested: The requested table definitions.
    :param actual: The actual schemas of the reused tables.
    :param table_ids: Mapping of requested table names to created table IDs.
    :return: Conflicts and next_steps keys, or an empty dict when every
        reused table satisfies the request.
    """

    requested_by_name = {table.name: table for table in requested}
    conflicts = _table_schema_conflicts(requested_by_name, actual, table_ids)
    if not conflicts:
        return {}

    missing_names = _missing_field_names(conflicts)
    missing_hint = (
        f" Missing fields: {', '.join(missing_names)}." if missing_names else ""
    )
    return {
        "incomplete_reused_tables": conflicts,
        "next_steps": (
            "Exact-name tables were reused, but their actual schemas in "
            "reused_tables do not satisfy the request."
            f"{missing_hint} Call create_fields with each table id and its "
            "missing_fields payload; use update_fields for supported field settings. "
            "Field types and link/lookup relations cannot be changed in place. Do "
            "not claim completion until every mismatch is resolved or accurately "
            "reported as unsupported."
        ),
    }
