from django.db.models import Q, Sum
from django.db.models.functions import Coalesce

from baserow.contrib.builder.elements.models import ImageElement
from baserow.core.usage.registries import (
    USAGE_UNIT_MB,
    UsageInMB,
    WorkspaceStorageUsageItemType,
)
from baserow.core.user_files.models import UserFile


class ImageElementWorkspaceStorageUsageItem(WorkspaceStorageUsageItemType):
    type = "image_element"

    def calculate_storage_usage_workspace(self, workspace_id: int) -> UsageInMB:
        image_elements = ImageElement.objects.filter(
            page__builder__workspace_id=workspace_id,
            page__trashed=False,
            page__builder__trashed=False,
        )

        usage_in_mb = (
            UserFile.objects.filter(Q(id__in=image_elements.values("image_file")))
            .values("size")
            .aggregate(sum=Coalesce(Sum("size") / USAGE_UNIT_MB, 0))["sum"]
        )

        return usage_in_mb
