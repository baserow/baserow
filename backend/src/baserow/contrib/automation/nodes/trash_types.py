from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationActionNode, AutomationNode
from baserow.contrib.automation.nodes.operations import (
    RestoreAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.registries import (
    ReplaceAutomationNodeTrashOperationType,
)
from baserow.contrib.automation.nodes.signals import automation_node_created
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.signals import automation_workflow_updated
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
        # We save the previous position for the restoration
        return trash_item.workflow.get_graph().get_position(trash_item)

    def trash(
        self,
        item_to_trash: AutomationActionNode,
        requesting_user: AbstractUser,
        trash_entry: TrashEntry,
    ):
        item_to_trash.workflow.get_graph().remove(item_to_trash)

        super().trash(item_to_trash, requesting_user, trash_entry)

    def restore(
        self,
        trashed_item: AutomationActionNode,
        trash_entry: TrashEntry,
    ):
        workflow = trashed_item.workflow

        # If we have we have a trash operation type, and it's not a replace operation...
        """if (
            trash_entry.trash_operation_type
            != ReplaceAutomationNodeTrashOperationType.type
        ):
            # If we're restoring a node, and it has a previous node output, ensure that
            # the output UUID matches one of the `uid` in the previous node's edges. If
            # the output isn't found, it means that the edge was deleted whilst the node
            # was trashed, and we cannot restore the node because it would create a
            # broken workflow.
            if trashed_item.previous_node_output and trashed_item.previous_node_id:
                previous_node = trashed_item.previous_node.specific
                if not previous_node.service.specific.edges.filter(
                    uid=trashed_item.previous_node_output
                ).exists():
                    raise TrashItemRestorationDisallowed(
                        "This automation node cannot be "
                        "restored as its branch has been deleted."
                    )"""

        super().restore(trashed_item, trash_entry)

        position_node_id, position, output = trash_entry.additional_restoration_data

        # TODO check the position node still exists otherwise we should move the node at
        # the end of the graph

        position_node = AutomationNodeHandler().get_node(position_node_id)

        workflow.get_graph().insert(trashed_item, position_node, position, output)

        automation_node_created.send(self, node=trashed_item, user=None)

        if trash_entry.get_operation_type().send_post_restore_created_signal:
            automation_workflow_updated.send(self, workflow=workflow, user=None)

    def permanently_delete_item(
        self, trashed_item: AutomationNode, trash_item_lookup_cache=None
    ):
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreAutomationNodeOperationType.type
