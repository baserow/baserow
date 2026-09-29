from typing import Iterable

from django.db.models import QuerySet

from baserow.contrib.automation.operations import ListAutomationWorkflowsOperationType
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.trash_types import (
    AutomationWorkflowTrashableItemType,
)
from baserow.core.registries import LastViewedItemType


class AutomationWorkflowLastViewedItemType(LastViewedItemType):
    type = "automation_workflow"
    model_class = AutomationWorkflow
    list_operation_type = ListAutomationWorkflowsOperationType.type

    def get_visible_queryset(self) -> QuerySet:
        # The default manager already leaves out workflows of a trashed automation
        # or workspace.
        return AutomationWorkflow.objects.all()

    def get_queryset_for_user(self, user_id: int) -> QuerySet:
        return (
            self.get_visible_queryset()
            .select_related("automation")
            .filter(automation__workspace__workspaceuser__user_id=user_id)
        )

    def get_application_id(self, instance) -> int:
        return instance.automation_id

    def get_workspace_id(self, instance) -> int:
        return instance.automation.workspace_id

    def get_item_ids_of_permanently_deleted(
        self, trash_item_type: str, trash_item
    ) -> Iterable[int]:
        if trash_item_type == AutomationWorkflowTrashableItemType.type:
            return [trash_item.id]
        return []
