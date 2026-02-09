from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from django_cte import With

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
        ).order_by()
        cover_files = form_views.exclude(cover_image_id__isnull=True).values(
            file_id=F("cover_image_id")
        )
        logo_files = form_views.exclude(logo_image_id__isnull=True).values(
            file_id=F("logo_image_id")
        )
        file_ids_cte = With(cover_files.union(logo_files))

        user_files_qs = file_ids_cte.join(
            UserFile, id=file_ids_cte.col.file_id
        ).with_cte(file_ids_cte)
        usage = user_files_qs.aggregate(sum=Coalesce(Sum("size") / USAGE_UNIT_MB, 0))[
            "sum"
        ]

        return usage or 0
