from baserow.contrib.database.operations import ListTablesDatabaseTableOperationType
from baserow.contrib.database.table.models import Table
from baserow.core.handler import CoreHandler


def get_all_tables(endpoint):
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
