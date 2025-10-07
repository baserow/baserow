from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.workflows.operations import (
    RestoreAutomationWorkflowOperationType,
)
from baserow.contrib.automation.workflows.signals import (
    automation_workflow_created,
    automation_workflow_deleted,
)
from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType


class AutomationWorkflowTrashableItemType(TrashableItemType):
    type = "automation_workflow"
    model_class = AutomationWorkflow

    def get_parent(self, trashed_item: AutomationWorkflow) -> any:
        return trashed_item.automation

    def get_name(self, trashed_item: AutomationWorkflow) -> str:
        return trashed_item.name

    def trash(
        self,
        item_to_trash: AutomationWorkflow,
        requesting_user,
        trash_entry: TrashEntry,
    ):
        super().trash(item_to_trash, requesting_user, trash_entry)
        automation_workflow_deleted.send(
            self,
            automation=item_to_trash.automation,
            workflow_id=item_to_trash.id,
            user=None,
        )

    def restore(
        self,
        trashed_item: AutomationWorkflow,
        trash_entry: TrashEntry,
    ):
        super().restore(trashed_item, trash_entry)
        automation_workflow_created.send(self, workflow=trashed_item, user=None)

    def permanently_delete_item(
        self, trashed_item: AutomationWorkflow, trash_item_lookup_cache=None
    ):
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreAutomationWorkflowOperationType.type
