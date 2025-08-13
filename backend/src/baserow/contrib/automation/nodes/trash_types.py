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
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed
from baserow.core.trash.registries import TrashableItemType


class AutomationNodeTrashableItemType(TrashableItemType):
    type = "automation_node"
    model_class = AutomationNode

    def get_parent(self, trashed_item: AutomationActionNode) -> AutomationWorkflow:
        return trashed_item.workflow

    def get_name(self, trashed_item: AutomationActionNode) -> str:
        return f"{trashed_item.get_type().type} ({trashed_item.id})"

    def get_additional_restoration_data(self, trash_item: AutomationActionNode):
        return {
            node.id: {"previous_node_output": node.previous_node_output}
            for node in trash_item.get_next_nodes()
            if node.previous_node_output
        }

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
        # follow this node, to point to the node before `item_to_trash`, and ensure
        # that the previous_node_output is set to the output of the node before.
        AutomationNodeHandler().update_previous_node(
            item_to_trash.previous_node, next_nodes, item_to_trash.previous_node_output
        )

        automation_node_deleted.send(
            self,
            workflow=item_to_trash.workflow,
            node_id=item_to_trash.id,
            user=requesting_user,
        )

    def restore(self, trashed_item: AutomationActionNode, trash_entry: TrashEntry):
        workflow = trashed_item.workflow
        next_nodes = list(
            AutomationNodeHandler().get_next_nodes(workflow, trashed_item.previous_node)
        )

        # If we're restoring a node, and it has a previous node output, ensure that
        # the output UUID matches one of the `uid` in the previous node's edges. If
        # the output isn't found, it means that the edge was deleted whilst the node
        # was trashed, and we cannot restore the node because it would create a broken
        # workflow.
        if trashed_item.previous_node_output and trashed_item.previous_node_id:
            previous_node = trashed_item.previous_node.specific
            if not previous_node.service.specific.edges.filter(
                uid=trashed_item.previous_node_output
            ).exists():
                raise TrashItemRestorationDisallowed(
                    "This automation node cannot be "
                    "restored as its branch has been deleted."
                )

        super().restore(trashed_item, trash_entry)

        # Determine if this restored node has one or more nodes after it. If it does,
        # we'll need to update their previous_node_id to point to `trashed_item.id`
        AutomationNodeHandler().update_previous_node(
            trashed_item,
            next_nodes,
        )

        # If the trashed item had any restoration data, then that means that
        # we have `previous_node_output` from next nodes to update.
        restoration_data = trash_entry.additional_restoration_data or {}
        if restoration_data:
            updates = []
            for next_node in next_nodes:
                # Do we have anything to restore for this next node? For defensive
                # programming purposes we double-check that the next node is present
                # in the old state's restoration data.
                node_restoration_data = restoration_data.get(str(next_node.id))
                if node_restoration_data is None:
                    continue
                next_node.previous_node_output = node_restoration_data[
                    "previous_node_output"
                ]
                updates.append(next_node)
            AutomationNode.objects.bulk_update(updates, ["previous_node_output"])

        automation_node_created.send(self, node=trashed_item, user=None)

    def permanently_delete_item(
        self, trashed_item: AutomationNode, trash_item_lookup_cache=None
    ):
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreAutomationNodeOperationType.type
