from typing import List

from baserow.contrib.database.api.rows.serializers import get_row_serializer_class
from baserow.contrib.database.operations import ListTablesDatabaseTableOperationType
from baserow.contrib.database.table.models import Table
from baserow.core.handler import CoreHandler
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.registries import OperationType
from baserow.core.types import PermissionCheck


def get_all_tables(endpoint: MCPEndpoint) -> List[Table]:
    """
    Returns all the tables that the user of the endpoint has access to and are within
    the scope of the workspace.

    :param endpoint: The endpoint where to get the tables for.
    :return: The tables that the endpoint user has access to.
    """

    workspace = endpoint.workspace
    tables_qs = Table.objects.filter(
        database__workspace_id=workspace.id,
        database__trashed=False,
    ).select_related("database__workspace")
    return list(
        CoreHandler().filter_queryset(
            endpoint.user,
            ListTablesDatabaseTableOperationType.type,
            tables_qs,
            workspace=workspace,
        )
    )


def remove_table_no_permission(
    endpoint: MCPEndpoint, tables: List[Table], operation_type: List[OperationType]
) -> List[Table]:
    """
    Helper method that filters out the tables where the user doesn't have
    `operation_type` permissions for. This can be used to nicely list what the user
    does have access to.

    :param endpoint: The MCPEndpoint where the user and workspace will be extracted
        from.
    :param tables: A list of tables where the permissions of the `operation_type` must
        be checked for.
    :param operation_type: The operation type where to check if the user has table
        permissions for.
    :return: An updated list, only containing the tables that the user has
        `operation_type` permissions for.
    """

    checks = [
        PermissionCheck(endpoint.user, operation_type.type, table) for table in tables
    ]
    results = CoreHandler().check_multiple_permissions(
        checks=checks, workspace=endpoint.workspace
    )
    return [check.context for check, outcome in results.items() if outcome]


def table_in_workspace_of_endpoint(endpoint: MCPEndpoint, table_id: int) -> bool:
    """
    Checks if the provided table_id belongs to the workspace of the endpoint.

    :param endpoint: The endpoint where to get the workspace for.
    :param table_id: The table id to check.
    :return: Whether the table belongs to the workspace.
    """

    return Table.objects.filter(
        id=table_id, database__workspace_id=endpoint.workspace.id
    ).exists()


def get_table_row_serializer(table):
    """
    Returns the serializer class for rows in the given table, using the user field
    names.

    :param table: The table to get the serializer for.
    :return: The serializer class for the table rows.
    """

    model = table.get_model()
    return get_row_serializer_class(model, user_field_names=True)
