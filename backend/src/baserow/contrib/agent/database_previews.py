"""
Names of what the Agent's database tools work on, resolved as the Agent identity
before a call runs.
"""

from typing import Any

from django.db.models import Count

from baserow.contrib.database.fields.models import Field, SelectOption
from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import (
    ListRowsDatabaseTableOperationType,
)
from baserow.contrib.database.tools.tables import get_database, permitted_tables
from baserow.core.db import specific_iterator
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.tools import ToolContext

SELECT_FIELD_TYPES = ("single_select", "multiple_select")


def table_reference(
    ctx: ToolContext, table_id: int
) -> tuple[Table | None, dict[str, Any]]:
    """
    :param ctx: The Agent identity and its workspace.
    :param table_id: A table the call names.
    :return: The table, with its database's name and its own when the identity
        can see it, as a duplicated database keeps every table's name. Else None
        and its ID as written, so the tool's own error explains it.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    table = tables.select_related("database").filter(id=table_id).first()
    if table is None:
        return None, {"table_id": table_id}
    return table, {"database": table.database.name, "table": table.name}


def table_names(ctx: ToolContext, table_ids: list[int]) -> dict[int, str]:
    """
    :param ctx: The Agent identity and its workspace.
    :param table_ids: Tables the call names.
    :return: The names of those the identity can see, by ID.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    return dict(tables.filter(id__in=table_ids).values_list("id", "name"))


def database_name(ctx: ToolContext, table_ids: list[int]) -> str | None:
    """
    :param ctx: The Agent identity and its workspace.
    :param table_ids: Tables a call worked on.
    :return: The name of the one database the identity sees them in, or None
        when they are in several or none.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    names = set(
        tables.filter(id__in=table_ids).values_list("database__name", flat=True)
    )
    return names.pop() if len(names) == 1 else None


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


def named_fields(
    ctx: ToolContext, field_ids: list[int]
) -> dict[int, tuple[str, str, str]]:
    """
    Resolve each field on its own, so two fields with the same name stay apart.

    :param ctx: The Agent identity and its workspace.
    :param field_ids: Fields the call names.
    :return: Each field's, its table's and its database's name, by field ID, for
        the fields the identity can see. The others keep their IDs, so the tool's
        own error explains them.
    """

    listed = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    found = list(
        Field.objects.filter(id__in=field_ids, table__in=listed).select_related(
            "table__database"
        )
    )
    tables = {found_field.table_id: found_field.table for found_field in found}
    permitted = {
        table.id
        for table in permitted_tables(
            ctx, tables.values(), ListFieldsOperationType.type
        )
    }
    return {
        found_field.id: (
            found_field.name,
            found_field.table.name,
            found_field.table.database.name,
        )
        for found_field in found
        if found_field.table_id in permitted
    }


def select_option_usage(
    ctx: ToolContext, option_ids: dict[int, list[int]]
) -> dict[int, dict[int, tuple[str, int | None]]]:
    """
    Resolve the options a field update renames or removes, with one row count
    query per field however many options it names.

    :param ctx: The Agent identity and its workspace.
    :param option_ids: The option IDs a call names, by select field ID.
    :return: Each option's current value and the number of rows using it, by
        option ID, by field ID. The count is None when the identity may not list the table's
        rows. Options of fields the identity can't see, or that aren't the
        field's, are left out, so they keep their IDs.
    """

    if not option_ids:
        return {}
    listed = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    found = [
        found_field
        for found_field in specific_iterator(
            Field.objects.filter(id__in=option_ids, table__in=listed).select_related(
                "table"
            )
        )
        if field_type_registry.get_by_model(found_field).type in SELECT_FIELD_TYPES
    ]
    if not found:
        return {}
    tables = {found_field.table_id: found_field.table for found_field in found}
    visible = {
        table.id
        for table in permitted_tables(
            ctx, tables.values(), ListFieldsOperationType.type
        )
    }
    readable = {
        table.id
        for table in permitted_tables(
            ctx,
            [tables[table_id] for table_id in visible],
            ListRowsDatabaseTableOperationType.type,
        )
    }
    found = [found_field for found_field in found if found_field.table_id in visible]
    options = SelectOption.objects.filter(
        field__in=found,
        id__in=[option_id for ids in option_ids.values() for option_id in ids],
    ).values_list("id", "field_id", "value")
    names = {option_id: (field_id, value) for option_id, field_id, value in options}

    usage = {}
    for found_field in found:
        named = [
            option_id
            for option_id in option_ids[found_field.id]
            if names.get(option_id, (None,))[0] == found_field.id
        ]
        if not named:
            continue
        counts = None
        if found_field.table_id in readable:
            model = found_field.table.get_model(
                fields=[found_field], field_ids=[], add_dependencies=False
            )
            column = found_field.db_column
            counts = dict(
                model.objects.filter(**{f"{column}__in": named})
                .values_list(column)
                .annotate(count=Count("id", distinct=True))
                .order_by()
            )
        usage[found_field.id] = {
            option_id: (
                names[option_id][1],
                None if counts is None else counts.get(option_id, 0),
            )
            for option_id in named
        }
    return usage


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
        empty, by row ID. When two of them read the same, every named row gets its
        ID too, which no other row's label can match. Rows that are missing or
        trashed, and all rows when the identity may not list them, keep their IDs.
    """

    if not permitted_tables(ctx, [table], ListRowsDatabaseTableOperationType.type):
        return {}
    names = RowHandler().get_row_names(table, row_ids)
    labels = {row_id: name or f"unnamed row {row_id}" for row_id, name in names.items()}
    if len(set(labels.values())) == len(labels):
        return labels
    return {
        row_id: f"{name} (row {row_id})" if name else labels[row_id]
        for row_id, name in names.items()
    }
