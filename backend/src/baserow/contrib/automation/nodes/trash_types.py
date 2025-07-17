from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
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
        return f"{trashed_item.get_type().type} ({trashed_item.id})"

    def trash(
        self,
        item_to_trash: AutomationActionNode,
        requesting_user,
        trash_entry: TrashEntry,
    ):
        # Determine if this node has a node after it. If it does, we'll
        # need to update its previous_node_id after `item_to_trash` is trashed.
        next_nodes = list(item_to_trash.get_next_nodes())

        super().trash(item_to_trash, requesting_user, trash_entry)

        # As `item_to_trash` is trashed, we need to update the nodes that immediately
        # follow this node, to point to the node before `item_to_trash`.
        AutomationNodeHandler().update_previous_node(
            item_to_trash.previous_node, next_nodes
        )

        automation_node_deleted.send(
            self,
            workflow=item_to_trash.workflow,
            node_id=item_to_trash.id,
            user=requesting_user,
        )

    def restore(self, trashed_item: AutomationActionNode, trash_entry: TrashEntry):
        next_nodes = list(
            AutomationNodeHandler().get_next_nodes(
                trashed_item.workflow, trashed_item.previous_node
            )
        )

        super().restore(trashed_item, trash_entry)

        # Determine if this restored node has a node after it. If it does, we'll
        # need to update its previous_node_id to point to `trashed_item.id`
        # TODO this works for now but as soon as we can add more branches, we'll have
        #      to store somewhere the next nodes when we trash the item
        AutomationNodeHandler().update_previous_node(trashed_item, next_nodes)

        automation_node_created.send(self, node=trashed_item, user=None)

    def permanently_delete_item(
        self, trashed_item: AutomationNode, trash_item_lookup_cache=None
    ):
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreAutomationNodeOperationType.type
