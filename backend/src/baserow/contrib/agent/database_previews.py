"""
Names of what the Agent's database tools work on, resolved as the Agent identity
before a call runs.
"""

from typing import Any

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import (
    ListRowsDatabaseTableOperationType,
)
from baserow.contrib.database.tools.tables import get_database, permitted_tables
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.tools import ToolContext


def table_reference(
    ctx: ToolContext, table_id: int
) -> tuple[Table | None, dict[str, Any]]:
    """
    :param ctx: The Agent identity and its workspace.
    :param table_id: A table the call names.
    :return: The table and its name when the identity can see it, else None and
        its ID as written, so the tool's own error explains it.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    table = tables.filter(id=table_id).first()
    if table is None:
        return None, {"table_id": table_id}
    return table, {"table": table.name}


def table_names(ctx: ToolContext, table_ids: list[int]) -> dict[int, str]:
    """
    :param ctx: The Agent identity and its workspace.
    :param table_ids: Tables the call names.
    :return: The names of those the identity can see, by ID.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    return dict(tables.filter(id__in=table_ids).values_list("id", "name"))


def database_reference(ctx: ToolContext, database_id: int) -> dict[str, Any]:
    """
    :param ctx: The Agent identity and its workspace.
    :param database_id: A database the call names.
    :return: Its name, or its ID as written when the identity can't see it.
    """

    try:
        return {"database": get_database(ctx, database_id).name}
    except ApplicationDoesNotExist:
        return {"database_id": database_id}


def named_fields(ctx: ToolContext, field_ids: list[int]) -> dict[int, tuple[str, str]]:
    """
    Resolve each field on its own, so two fields with the same name stay apart.

    :param ctx: The Agent identity and its workspace.
    :param field_ids: Fields the call names.
    :return: Each field's name and its table's name, by field ID, for the fields
        the identity can see. The others keep their IDs, so the tool's own error
        explains them.
    """

    listed = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    found = list(
        Field.objects.filter(id__in=field_ids, table__in=listed).select_related("table")
    )
    tables = {found_field.table_id: found_field.table for found_field in found}
    permitted = {
        table.id
        for table in permitted_tables(
            ctx, tables.values(), ListFieldsOperationType.type
        )
    }
    return {
        found_field.id: (found_field.name, found_field.table.name)
        for found_field in found
        if found_field.table_id in permitted
    }


def table_field_names(ctx: ToolContext, table: Table) -> dict[int, str]:
    """
    :param ctx: The Agent identity and its workspace.
    :param table: A table the identity can see.
    :return: Its field names by ID, or nothing when the identity may not list its
        fields, so the request keeps the IDs as written.
    """

    if not permitted_tables(ctx, [table], ListFieldsOperationType.type):
        return {}
    return dict(Field.objects.filter(table=table).values_list("id", "name"))


def readable_names(table: Table) -> set[str]:
    """
    :param table: The table the call writes to.
    :return: The names of its fields that aren't trashed or write-only, the only
        ones whose values are shown.
    """

    return {
        table_field.name
        for table_field in Field.objects.filter(table=table)
        if not field_type_registry.get_by_model(table_field.specific_class).write_only
    }


def row_names(ctx: ToolContext, table: Table, row_ids: list[int]) -> dict[int, str]:
    """
    :param ctx: The Agent identity and its workspace.
    :param table: A table the identity can see.
    :param row_ids: Rows the call names.
    :return: Each row's primary value as text, or ``unnamed row <id>`` when it's
        empty, by row ID. Rows that are missing or trashed, and all rows when the
        identity may not list them, keep their IDs.
    """

    if not permitted_tables(ctx, [table], ListRowsDatabaseTableOperationType.type):
        return {}
    names = RowHandler().get_row_names(table, row_ids)
    return {row_id: name or f"unnamed row {row_id}" for row_id, name in names.items()}
