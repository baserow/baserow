from typing import List

from baserow.contrib.database.operations import ListTablesDatabaseTableOperationType
from baserow.contrib.database.table.models import Table
from baserow.core.handler import CoreHandler
from baserow.core.mcp import MCPEndpoint
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
        database__workspace_id=workspace.id
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
):
    """
    @TODO docs and write tests for this.

    :param endpoint:
    :param tables:
    :param operation_type:
    :return:
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
