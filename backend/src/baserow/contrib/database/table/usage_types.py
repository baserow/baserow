from django.db.models import Sum
from django.db.models.functions import Coalesce

from baserow.core.usage.registries import UsageInMB, WorkspaceStorageUsageItemType

from .handler import TableHandler, TableUsageHandler


class TableWorkspaceStorageUsageItemType(WorkspaceStorageUsageItemType):
    type = "table"

    def calculate_storage_usage_instance(self):
        # ensure all pending updates are applied first
        TableUsageHandler.update_tables_usage()

    def calculate_storage_usage_workspace(self, workspace_id: int) -> UsageInMB:
        # Aggregate all the tables storage usage in the workspace
        return (
            TableHandler.get_tables()
            .filter(database__workspace_id=workspace_id)
            .aggregate(sum=Coalesce(Sum("usage__storage_usage"), 0))["sum"]
        )
