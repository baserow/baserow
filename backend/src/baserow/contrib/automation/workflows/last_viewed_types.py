from typing import Iterable

from django.db.models import QuerySet

from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.trash_types import (
    AutomationWorkflowTrashableItemType,
)
from baserow.core.registries import LastViewedItemType


class AutomationWorkflowLastViewedItemType(LastViewedItemType):
    type = "automation_workflow"
    model_class = AutomationWorkflow

    def get_queryset_for_user(self, user_id: int) -> QuerySet:
        return AutomationWorkflow.objects.select_related("automation").filter(
            automation__trashed=False,
            automation__workspace__workspaceuser__user_id=user_id,
        )

    def get_application_id(self, instance: AutomationWorkflow) -> int:
        return instance.automation_id

    def get_workspace_id(self, instance: AutomationWorkflow) -> int:
        return instance.automation.workspace_id

    def get_item_ids_of_permanently_deleted(
        self, trash_item_type: str, trash_item
    ) -> Iterable[int]:
        if trash_item_type == AutomationWorkflowTrashableItemType.type:
            return [trash_item.id]
        return []
