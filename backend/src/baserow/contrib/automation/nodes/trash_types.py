from typing import List, Optional

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
from baserow.core.graph.models import GraphPointTrashableItemType
from baserow.core.models import TrashEntry
from baserow.core.trash.exceptions import TrashItemRestorationDisallowed


class AutomationNodeTrashableItemType(GraphPointTrashableItemType):
    """
    Trashable item type for `AutomationNode`.

    The graph-aware trash/restore behaviour (removing the node from its workflow
    graph, cascading to its children and re-inserting everything on restore) is
    inherited from `GraphPointTrashableItemType`. This class layers on the
    automation-specific concerns:

    - Skipping the graph mutation during a node "replace" (see `should_mutate_graph`),
    - Not running the container guard while cascading (see `before_cascade_delete`),
    - Rejecting a restore whose reference branch/output no longer exists (see
      `validate_reference`),
    - Emitting the node/workflow realtime signals and invalidating the workflow's
      node cache.
    """

    type = "automation_node"
    model_class = AutomationNode

    def get_parent(self, trashed_item: AutomationActionNode) -> AutomationWorkflow:
        return trashed_item.workflow

    def get_restore_operation_type(self) -> str:
        return RestoreAutomationNodeOperationType.type

    def should_mutate_graph(self, trash_entry: TrashEntry) -> bool:
        """
        A "replace" rearranges the graph itself (swapping one node for another), so
        trash/restore must not also remove/insert the node.
        """

        return (
            trash_entry.trash_operation_type
            != ReplaceAutomationNodeTrashOperationType.type
        )

    def before_cascade_delete(self, descendant: AutomationNode):
        """
        Container nodes guard against deletion while they still have children
        (raising `AutomationNodeNotDeletable`). During a trash cascade the whole
        subtree is soft-deleted together, so we skip that per-descendant guard.
        """

    def validate_reference(self, reference: Optional[AutomationNode], output: str):
        """
        The reference node's output must still exist for the node to re-attach to
        it; the branch it was on may have been deleted in the meantime.
        """

        if (
            reference is not None
            and output
            not in reference.service.get_type().get_edges(reference.service.specific)
        ):
            raise TrashItemRestorationDisallowed(
                "This automation node cannot be restored as its branch has been deleted."
            )

    def trash(
        self,
        item_to_trash: AutomationActionNode,
        requesting_user: AbstractUser,
        trash_entry: TrashEntry,
    ):
        """
        Trash the node via the base graph logic, then (unless this is a replace)
        notify clients the workflow changed, and invalidate the node cache.
        """

        super().trash(item_to_trash, requesting_user, trash_entry)

        if self.should_mutate_graph(trash_entry):
            item_to_trash.workflow.refresh_from_db()
            automation_workflow_updated.send(
                self, workflow=item_to_trash.workflow, user=requesting_user
            )

        AutomationNodeHandler().invalidate_node_cache(item_to_trash.workflow)

    def restore(
        self,
        trashed_item: AutomationActionNode,
        trash_entry: TrashEntry,
    ):
        """
        Restore the node (and any cascaded children) via the base graph logic,
        invalidate the node cache, then (unless this is a replace) broadcast each
        restored node and the updated workflow.
        """

        restored_nodes: List[AutomationNode] = super().restore(
            trashed_item, trash_entry
        )

        AutomationNodeHandler().invalidate_node_cache(trashed_item.workflow)

        if self.should_mutate_graph(trash_entry):
            for node in restored_nodes:
                automation_node_created.send(self, node=node, user=None)
            automation_workflow_updated.send(
                self, workflow=trashed_item.workflow, user=None
            )
