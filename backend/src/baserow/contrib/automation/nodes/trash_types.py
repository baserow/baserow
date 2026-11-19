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
from baserow.core.trash.handler import TrashHandler


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

    @classmethod
    def split_outputs_on_restore(
        cls,
        node_id: int,
        next_output: str,
        moved_node_ids: list[int],
        joined_node_ids: list[int],
    ):
        """
        Note on a trashed node's entry that, once restored, the nodes an insert
        moved to `next_output` go back there. Undoing the insert joined them onto
        the default output, before `joined_node_ids`.

        :param node_id: The ID of the trashed node.
        :param next_output: The output the nodes move back to.
        :param moved_node_ids: The nodes the insert moved to `next_output`.
        :param joined_node_ids: The nodes that were on the default output before
            the join, which stay there.
        """

        trash_entry = TrashHandler.get_trash_entry(cls.type, node_id)
        trash_entry.additional_restoration_data = {
            **trash_entry.additional_restoration_data,
            "next_output": next_output,
            "moved_node_ids": moved_node_ids,
            "joined_node_ids": joined_node_ids,
        }
        trash_entry.save(update_fields=["additional_restoration_data"])

    def _split_outputs(self, node: AutomationNode, data: dict):
        """
        Move the nodes the insert moved back to their output: the run of them at
        the start of the default output, so a node added since stays where it is.

        :raises TrashItemRestorationDisallowed: When the default output starts
            with a node that is neither one of them nor one that was there.
        """

        moved_ids = data.get("moved_node_ids", [])
        chain = node.workflow.get_graph().get_chain_ids(node, "")
        if chain and int(chain[0]) not in {*moved_ids, *data["joined_node_ids"]}:
            raise TrashItemRestorationDisallowed(
                f"This automation node cannot be restored: node {chain[0]} was put "
                "before the nodes it had on its branch, and would then run only "
                "when the branch matches."
            )
        node.workflow.get_graph().split_next_points(
            node, "", data["next_output"], moved_ids
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

        data = trash_entry.additional_restoration_data
        if (
            self.should_mutate_graph(trash_entry)
            and isinstance(data, dict)
            and data.get("next_output")
        ):
            self._split_outputs(trashed_item, data)

        AutomationNodeHandler().invalidate_node_cache(trashed_item.workflow)

        if self.should_mutate_graph(trash_entry):
            for node in restored_nodes:
                automation_node_created.send(self, node=node, user=None)
            automation_workflow_updated.send(
                self, workflow=trashed_item.workflow, user=None
            )
