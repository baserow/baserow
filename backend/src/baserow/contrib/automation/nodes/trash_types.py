from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType

from baserow.contrib.automation.nodes.signals import (
    automation_node_created,
    automation_node_deleted,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.operations import RestoreAutomationNodeOperationType


class AutomationNodeTrashableItemType(TrashableItemType):
    type = "automation_node"
    model_class = AutomationNode

    def get_parent(self, trashed_item: AutomationNode) -> any:
        return trashed_item.workflow

    def get_name(self, trashed_item: AutomationNode) -> str:
        return f"Node {trashed_item.id}"

    def trash(
        self,
        item_to_trash: AutomationNode,
        requesting_user,
        trash_entry: TrashEntry,
    ):
        super().trash(item_to_trash, requesting_user, trash_entry)
        automation_node_deleted.send(
            self,
            automation=item_to_trash.workflow.automation,
            node_id=item_to_trash.id,
            user=None,
        )

    def restore(self, trashed_item: AutomationNode, trash_entry: TrashEntry):
        super().restore(trashed_item, trash_entry)
        automation_node_created.send(self, node=trashed_item, user=None)

    def permanently_delete_item(
        self, trashed_item: AutomationNode, trash_item_lookup_cache=None
    ):
        AutomationNodeHandler().delete_node(trashed_item)

    def get_restore_operation_type(self) -> str:
        return RestoreAutomationNodeOperationType.type
