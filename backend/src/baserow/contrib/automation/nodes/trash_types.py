from baserow.contrib.automation.nodes.models import AutomationActionNode, AutomationNode
from baserow.contrib.automation.nodes.operations import (
    RestoreAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.signals import (
    automation_node_created,
    automation_node_deleted,
)
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.models import TrashEntry
from baserow.core.trash.registries import TrashableItemType


class AutomationNodeTrashableItemType(TrashableItemType):
    type = "automation_node"
    model_class = AutomationNode

    def get_parent(self, trashed_item: AutomationActionNode) -> AutomationWorkflow:
        return trashed_item.workflow

    def get_name(self, trashed_item: AutomationActionNode) -> str:
        return f"{trashed_item.specific.get_type().type} ({trashed_item.id})"

    def trash(
        self,
        item_to_trash: AutomationActionNode,
        requesting_user,
        trash_entry: TrashEntry,
    ):
        # Determine if this node has a node after it. If it does, we'll
        # need to update its previous_node_id after `item_to_trash` is trashed.
        next_nodes = item_to_trash.get_next_nodes()

        super().trash(item_to_trash, requesting_user, trash_entry)

        for next_node in next_nodes:
            # As `item_to_trash` is trashed, we need to update `next_node`'s
            # previous_node_id to point to the node before `item_to_trash`.
            next_node.previous_node_id = item_to_trash.previous_node_id
            next_node.save(update_fields=["previous_node_id"])

        automation_node_deleted.send(
            self,
            workflow=item_to_trash.workflow,
            node_id=item_to_trash.id,
            user=requesting_user,
        )

    def restore(self, trashed_item: AutomationActionNode, trash_entry: TrashEntry):
        super().restore(trashed_item, trash_entry)

        # Determine if this restored node has a node after it. If it does, we'll
        # need to update its previous_node_id to point to `trashed_item.id`
        next_nodes = AutomationNode.objects.exclude(id=trashed_item.id).filter(
            workflow=trashed_item.workflow,
            previous_node_id=trashed_item.previous_node_id,
        )
        for next_node in next_nodes:
            next_node.previous_node_id = trashed_item.id
            next_node.save(update_fields=["previous_node_id"])

        automation_node_created.send(self, node=trashed_item, user=None)

    def permanently_delete_item(
        self, trashed_item: AutomationNode, trash_item_lookup_cache=None
    ):
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreAutomationNodeOperationType.type
