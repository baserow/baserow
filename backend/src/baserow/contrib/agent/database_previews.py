"""
Names of what the Agent's database tools work on, resolved as the Agent identity
before a call runs.
"""

from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import (
    ListRowsDatabaseTableOperationType,
)
from baserow.contrib.database.tools.tables import (
    get_database,
    get_table,
    permitted_tables,
)
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolNotFoundError


def visible_table(ctx: ToolContext, table_id: int) -> Table:
    """
    :param ctx: The Agent identity and its workspace.
    :param table_id: A table the call names.
    :return: The table, when the identity can see it.
    :raises Table.DoesNotExist: When it can't.
    """

    return (
        TableHandler().list_workspace_tables(ctx.user, ctx.workspace).get(id=table_id)
    )


def table_names(ctx: ToolContext, table_ids: list[int]) -> dict[int, str]:
    """
    :param ctx: The Agent identity and its workspace.
    :param table_ids: Tables the call names.
    :return: The names of those the identity can see, by ID.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    return dict(tables.filter(id__in=table_ids).values_list("id", "name"))


def database_name(ctx: ToolContext, database_id: int) -> str:
    """
    :param ctx: The Agent identity and its workspace.
    :param database_id: A database the call names.
    :return: Its name.
    :raises ApplicationDoesNotExist: When the identity can't see it.
    """

    return get_database(ctx, database_id).name


def named_fields(ctx: ToolContext, field_ids: list[int]) -> dict[int, tuple[str, str]]:
    """
    Resolve each field on its own, so two fields with the same name stay apart.

    :param ctx: The Agent identity and its workspace.
    :param field_ids: Fields the call names.
    :return: Each field's name and its table's name, by field ID.
    :raises ToolNotFoundError: When the identity can't see one of them.
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
    names = {
        found_field.id: (found_field.name, found_field.table.name)
        for found_field in found
        if found_field.table_id in permitted
    }
    missing = [
        field_id for field_id in dict.fromkeys(field_ids) if field_id not in names
    ]
    if missing:
        raise ToolNotFoundError(
            f"Fields {missing} were not found. Call get_table_schema for the "
            "current field IDs."
        )
    return names


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


def table_with_rows(ctx: ToolContext, table_id: int) -> Table:
    """
    :param ctx: The Agent identity and its workspace.
    :param table_id: The table whose rows the call names.
    :return: The table, when the identity may list its rows.
    :raises Table.DoesNotExist: When the identity can't see it.
    :raises PermissionDenied: When it may not list its rows.
    """

    return get_table(ctx, table_id, ListRowsDatabaseTableOperationType.type)


def row_names(table: Table, row_ids: list[int]) -> dict[int, str]:
    """
    :param table: A table whose rows the identity may list.
    :param row_ids: Rows the call names.
    :return: Each row's primary value as text, or ``unnamed row <id>`` when it's
        empty, by row ID.
    :raises ToolNotFoundError: When a row is missing or trashed.
    """

    names = RowHandler().get_row_names(table, row_ids)
    missing = [row_id for row_id in dict.fromkeys(row_ids) if row_id not in names]
    if missing:
        raise ToolNotFoundError(
            f"Rows {missing} were not found in table {table.id}. Call "
            "list_table_rows for the current row IDs."
        )
    return {row_id: names[row_id] or f"unnamed row {row_id}" for row_id in row_ids}
