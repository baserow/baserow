"""
Shared database service layer.

Provides workspace-scoped access to databases, tables, fields, and rows.

All functions accept ``user`` and ``workspace`` and apply permission filtering
so callers never need to worry about permissions or cross-workspace access.
"""

from typing import Any

from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.core.db import specific_iterator
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace

# ---------------------------------------------------------------------------
# Query helpers (shared with enterprise assistant)
# ---------------------------------------------------------------------------


def filter_tables(user: AbstractUser, workspace: Workspace):
    """Return all tables visible to the user in the given workspace."""
    return TableHandler().list_workspace_tables(user, workspace)


def get_table(user: AbstractUser, workspace: Workspace, table_id: int) -> Table:
    """
    Return a single table by ID, verifying workspace access.

    :raises Table.DoesNotExist: if the table is not found or not accessible.
    """
    return filter_tables(user, workspace).get(id=table_id)


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------


def list_databases(user: AbstractUser, workspace: Workspace) -> list:
    """
    Return all databases in the workspace that the user can see.

    :returns: List of Database instances, ordered by (order, id).
    """
    from baserow.contrib.database.models import Database
    from baserow.core.operations import ListApplicationsWorkspaceOperationType

    qs = Database.objects.filter(
        workspace=workspace,
        workspace__trashed=False,
        trashed=False,
    ).order_by("order", "id")

    return list(
        CoreHandler().filter_queryset(
            user,
            ListApplicationsWorkspaceOperationType.type,
            qs,
            workspace=workspace,
        )
    )


def get_database(user: AbstractUser, workspace: Workspace, database_id: int):
    """
    Return a single database by ID, verifying workspace access.

    :raises Database.DoesNotExist: if not found or not accessible.
    """
    from baserow.contrib.database.models import Database
    from baserow.core.operations import ListApplicationsWorkspaceOperationType

    qs = Database.objects.filter(
        workspace=workspace,
        workspace__trashed=False,
        trashed=False,
        id=database_id,
    )
    return (
        CoreHandler()
        .filter_queryset(
            user, ListApplicationsWorkspaceOperationType.type, qs, workspace=workspace
        )
        .get()
    )


def create_database(user: AbstractUser, workspace: Workspace, name: str):
    """
    Create a new database in the workspace.

    :returns: The created Database instance.
    """
    from baserow.core.actions import CreateApplicationActionType

    return CreateApplicationActionType.do(user, workspace, "database", name=name)


# ---------------------------------------------------------------------------
# Table operations
# ---------------------------------------------------------------------------


def list_tables(
    user: AbstractUser, workspace: Workspace, database_id: int | None = None
) -> list[Table]:
    """
    Return all tables visible to the user in the workspace.

    :param database_id: If provided, restrict to tables in this database.
    :returns: List of Table instances.
    """
    qs = filter_tables(user, workspace)
    if database_id is not None:
        qs = qs.filter(database_id=database_id)
    return list(qs)


def get_table_schema(
    user: AbstractUser, workspace: Workspace, table_ids: list[int]
) -> list[dict]:
    """
    Return field schemas for the given tables.

    :returns: List of dicts ``{id, name, database_id, fields: [...]}``.
              Each field dict includes ``id``, ``name``, ``type``, ``primary``
              and type-specific extras (select_options, link_row_table_id, etc.).
    """
    tables = {
        t.id: t
        for t in filter_tables(user, workspace)
        .filter(id__in=table_ids)
        .select_related("database")
    }

    valid_table_ids = [tid for tid in table_ids if tid in tables]
    if not valid_table_ids:
        return []

    all_fields = list(
        specific_iterator(
            FieldHandler()
            .get_base_fields_queryset()
            .filter(table_id__in=valid_table_ids)
            .order_by("table_id", "-primary", "order", "id"),
            per_content_type_queryset_hook=(
                lambda model, queryset: field_type_registry.get_by_model(
                    model
                ).enhance_field_queryset(queryset, model)
            ),
        )
    )

    fields_by_table: dict[int, list] = {}
    for field in all_fields:
        fields_by_table.setdefault(field.table_id, []).append(field)

    return [
        {
            "id": tables[tid].id,
            "name": tables[tid].name,
            "database_id": tables[tid].database_id,
            "fields": [_serialize_field(f) for f in fields_by_table.get(tid, [])],
        }
        for tid in valid_table_ids
    ]


def _serialize_field(field) -> dict:
    """Convert a specific field instance to a plain dict for schema output."""
    from baserow.contrib.database.fields.models import (
        DateField,
        FormulaField,
        LinkRowField,
        MultipleSelectField,
        NumberField,
        RatingField,
        SingleSelectField,
    )

    field_type = field_type_registry.get_by_model(field)
    data: dict[str, Any] = {
        "id": field.id,
        "name": field.name,
        "type": field_type.type,
        "primary": field.primary,
    }

    if isinstance(field, (SingleSelectField, MultipleSelectField)):
        data["select_options"] = [
            {"id": opt.id, "value": opt.value, "color": opt.color}
            for opt in field.select_options.all()
        ]
    elif isinstance(field, LinkRowField):
        data["link_row_table_id"] = field.link_row_table_id
        linked = field.link_row_table
        data["link_row_table_name"] = linked.name if linked else None
    elif isinstance(field, NumberField):
        data["number_decimal_places"] = field.number_decimal_places
    elif isinstance(field, DateField):
        data["date_include_time"] = field.date_include_time
        data["date_force_timezone"] = field.date_force_timezone
    elif isinstance(field, FormulaField):
        data["formula"] = field.formula
        data["formula_type"] = field.formula_type
    elif isinstance(field, RatingField):
        data["max_value"] = field.max_value

    return data


# Dependency order for field creation: regular → link_row → lookup → formula.
_FIELD_CREATION_ORDER: dict[str, int] = {
    "link_row": 1,
    "lookup": 2,
    "formula": 3,
}


def create_table(
    user: AbstractUser,
    workspace: Workspace,
    database_id: int,
    name: str,
    fields: list[dict] | None = None,
) -> dict:
    """
    Create a table in the given database, optionally with additional fields.

    ``fields`` is a list of dicts with at minimum ``name`` and ``type``.
    Other keys are passed as kwargs to ``CreateFieldActionType.do()``.

    :returns: Dict with the created table and its fields.
    """
    from baserow.contrib.database.fields.actions import CreateFieldActionType
    from baserow.contrib.database.table.actions import CreateTableActionType

    database = get_database(user, workspace, database_id)
    table, _ = CreateTableActionType.do(user, database, name, fill_example=False)

    created_fields = []
    if fields:
        sorted_fields = sorted(
            fields, key=lambda f: _FIELD_CREATION_ORDER.get(f.get("type", "text"), 0)
        )
        for src_field_spec in sorted_fields:
            field_spec = dict(src_field_spec)
            type_name = field_spec.pop("type")
            created = CreateFieldActionType.do(user, table, type_name, **field_spec)
            created_fields.append(_serialize_field(created))

    return {
        "id": table.id,
        "name": table.name,
        "database_id": table.database_id,
        "fields": created_fields,
    }


def update_table(
    user: AbstractUser, workspace: Workspace, table_id: int, name: str
) -> dict:
    """Rename a table."""
    from baserow.contrib.database.table.actions import UpdateTableActionType

    table = get_table(user, workspace, table_id)
    UpdateTableActionType.do(user, table, name=name)
    # UpdateTableActionType mutates table in-place via the handler
    return {"id": table.id, "name": table.name, "database_id": table.database_id}


def delete_table(user: AbstractUser, workspace: Workspace, table_id: int) -> None:
    """Delete (trash) a table."""
    from baserow.contrib.database.table.actions import DeleteTableActionType

    table = get_table(user, workspace, table_id)
    DeleteTableActionType.do(user, table)


# ---------------------------------------------------------------------------
# Field operations
# ---------------------------------------------------------------------------


def get_field(user: AbstractUser, workspace: Workspace, field_id: int):
    """
    Return a locked specific field by ID, verifying workspace access.

    :raises Field.DoesNotExist: if not found or outside workspace.
    """

    try:
        field = Field.objects.select_related("table__database").get(id=field_id)
    except Field.DoesNotExist:
        raise
    if field.table.database.workspace_id != workspace.id:
        raise Field.DoesNotExist(f"Field {field_id} not in workspace.")
    if not filter_tables(user, workspace).filter(id=field.table_id).exists():
        raise Field.DoesNotExist(f"Field {field_id} not accessible.")
    return FieldHandler().get_specific_field_for_update(field_id)


def create_fields(
    user: AbstractUser, workspace: Workspace, table_id: int, fields: list[dict]
) -> list[dict]:
    """
    Create one or more fields in a table.

    Each dict in ``fields`` must have ``name`` and ``type``; other keys are
    passed as kwargs to ``CreateFieldActionType.do()``.

    Fields are created in dependency order (regular → link_row → lookup → formula).

    :returns: List of serialized created field dicts.
    """
    from baserow.contrib.database.fields.actions import CreateFieldActionType

    table = get_table(user, workspace, table_id)
    sorted_fields = sorted(
        fields, key=lambda f: _FIELD_CREATION_ORDER.get(f.get("type", "text"), 0)
    )
    created = []
    for src_field_spec in sorted_fields:
        field_spec = dict(src_field_spec)
        type_name = field_spec.pop("type")
        field = CreateFieldActionType.do(user, table, type_name, **field_spec)
        created.append(_serialize_field(field))
    return created


def update_fields(
    user: AbstractUser, workspace: Workspace, fields: list[dict]
) -> list[dict]:
    """
    Update one or more fields.

    Each dict must have ``id``; other keys are passed to ``UpdateFieldActionType.do()``.

    :returns: List of serialized updated field dicts.
    """
    from baserow.contrib.database.fields.actions import UpdateFieldActionType

    updated = []
    for src_field_spec in fields:
        field_spec = dict(src_field_spec)
        field_id = field_spec.pop("id")
        new_type_name = field_spec.pop("type", None)
        field = get_field(user, workspace, field_id)
        result, _ = UpdateFieldActionType.do(
            user, field, new_type_name=new_type_name, **field_spec
        )
        updated.append(_serialize_field(result))
    return updated


def delete_fields(
    user: AbstractUser, workspace: Workspace, field_ids: list[int]
) -> None:
    """Delete (trash) a list of fields by ID."""
    from baserow.contrib.database.fields.actions import DeleteFieldActionType

    for field_id in field_ids:
        field = get_field(user, workspace, field_id)
        DeleteFieldActionType.do(user, field)


# ---------------------------------------------------------------------------
# Row operations
# ---------------------------------------------------------------------------


def list_rows(
    user: AbstractUser,
    workspace: Workspace,
    table_id: int,
    search: str = "",
    page: int = 1,
    size: int = 100,
) -> dict:
    """
    Return a paginated list of rows from a table, with user field names.

    :returns: Dict with ``count`` and ``results`` (list of row dicts).
    """
    from django.conf import settings

    from baserow.contrib.database.api.rows.serializers import (
        serialize_rows_for_response,
    )

    # Clamp pagination parameters to safe bounds.
    page = max(1, page)
    size = max(1, min(size, settings.ROW_PAGE_SIZE_LIMIT))

    table = get_table(user, workspace, table_id)
    model = table.get_model()
    qs = model.objects.filter(trashed=False).order_by("order", "id")

    if search:
        qs = qs.search_all_fields(search)

    count = qs.count()
    offset = (page - 1) * size
    rows = list(qs[offset : offset + size])

    data = serialize_rows_for_response(rows, model, user_field_names=True)
    return {"count": count, "results": list(data)}


def _map_user_field_names(model, rows: list[dict]) -> list[dict]:
    """
    Convert user field names to internal column names.

    e.g. ``{"Name": "John"}`` → ``{"field_1": "John"}``.

    :raises ValueError: if a field name is not recognised.
    """
    name_to_col = {
        info["field"].name: info["name"] for info in model._field_objects.values()
    }
    result = []
    for row in rows:
        converted: dict[str, Any] = {}
        for key, value in row.items():
            if key == "id":
                converted["id"] = value
            elif key in name_to_col:
                converted[name_to_col[key]] = value
            else:
                available = list(name_to_col.keys())
                raise ValueError(
                    f"Unknown field name '{key}'. Available fields: {available}"
                )
        result.append(converted)
    return result


def create_rows(
    user: AbstractUser, workspace: Workspace, table_id: int, rows: list[dict]
) -> list[dict]:
    """
    Create rows in a table using user field names.

    :param rows: List of dicts mapping user field name → value.
    :returns: List of created row dicts with user field names.
    """
    from baserow.contrib.database.api.rows.serializers import (
        serialize_rows_for_response,
    )
    from baserow.contrib.database.rows.actions import CreateRowsActionType

    table = get_table(user, workspace, table_id)
    model = table.get_model()
    rows_values = _map_user_field_names(model, rows)
    created = CreateRowsActionType.do(user, table, rows_values, model=model)
    return list(serialize_rows_for_response(created, model, user_field_names=True))


def update_rows(
    user: AbstractUser, workspace: Workspace, table_id: int, rows: list[dict]
) -> list[dict]:
    """
    Update rows in a table using user field names.

    Each dict in ``rows`` must include ``id`` plus the fields to update.

    :returns: List of updated row dicts with user field names.
    """
    from baserow.contrib.database.api.rows.serializers import (
        serialize_rows_for_response,
    )
    from baserow.contrib.database.rows.actions import UpdateRowsActionType

    table = get_table(user, workspace, table_id)
    model = table.get_model()
    rows_values = _map_user_field_names(model, rows)
    with transaction.atomic():
        result = UpdateRowsActionType.do(user, table, rows_values, model=model)
    return list(
        serialize_rows_for_response(result.updated_rows, model, user_field_names=True)
    )


def delete_rows(
    user: AbstractUser, workspace: Workspace, table_id: int, row_ids: list[int]
) -> None:
    """Delete rows by ID."""
    from baserow.contrib.database.rows.actions import DeleteRowsActionType

    table = get_table(user, workspace, table_id)
    DeleteRowsActionType.do(user, table, row_ids)
