from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from baserow.contrib.database.views.models import FormView
from baserow.core.usage.registries import (
    USAGE_UNIT_MB,
    UsageInMB,
    WorkspaceStorageUsageItemType,
)
from baserow.core.user_files.models import UserFile


class FormViewWorkspaceStorageUsageItem(WorkspaceStorageUsageItemType):
    type = "form_view"

    def calculate_storage_usage_workspace(self, workspace_id: int) -> UsageInMB:
        form_views = FormView.objects.filter(
            table__database__workspace_id=workspace_id,
            table__trashed=False,
            table__database__trashed=False,
        )

        usage = (
            UserFile.objects.filter(
                Q(id__in=form_views.values("cover_image"))
                | Q(id__in=form_views.values("logo_image"))
            )
            .values("size")
            .aggregate(sum=Coalesce(Sum("size") / USAGE_UNIT_MB, 0))["sum"]
        )

        return usage or 0
