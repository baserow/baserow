from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.operations import (
    RestoreAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.signals import (
    automation_node_created,
    automation_node_deleted,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType


class AutomationNodeTrashableItemType(TrashableItemType):
    type = "automation_node"
    model_class = AutomationNode

    def get_parent(self, trashed_item: AutomationNode) -> any:
        return trashed_item.workflow

    def get_name(self, trashed_item: AutomationNode) -> str:
        return f"{trashed_item.specific.get_type().type} ({trashed_item.id})"

    def trash(
        self,
        item_to_trash: AutomationNode,
        requesting_user,
        trash_entry: TrashEntry,
    ):
        super().trash(item_to_trash, requesting_user, trash_entry)

        # When an automation node is trashed, re-calculate the workflow's hierarchy.
        AutomationWorkflowHandler().update_node_hierarchy(item_to_trash.workflow)

        automation_node_deleted.send(
            self,
            workflow=item_to_trash.workflow,
            node_id=item_to_trash.id,
            user=requesting_user,
        )

    def restore(self, trashed_item: AutomationNode, trash_entry: TrashEntry):
        super().restore(trashed_item, trash_entry)
        # When a trashed automation node is restored,
        # re-calculate the workflow's hierarchy.
        AutomationWorkflowHandler().update_node_hierarchy(trashed_item.workflow)
        automation_node_created.send(self, node=trashed_item, user=None)

    def permanently_delete_item(
        self, trashed_item: AutomationNode, trash_item_lookup_cache=None
    ):
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreAutomationNodeOperationType.type
