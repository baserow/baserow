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

from .exceptions import AutomationNodeDoesNotExist


class AutomationNodeTrashableItemType(TrashableItemType):
    type = "automation_node"
    model_class = AutomationNode

    def get_parent(self, trashed_item: AutomationActionNode) -> AutomationWorkflow:
        return trashed_item.workflow

    def get_name(self, trashed_item: AutomationActionNode) -> str:
        return f"{trashed_item.get_type().type} ({trashed_item.id})"

    def get_additional_restoration_data(self, trashed_item: AutomationActionNode):
        # We save the previous position for the restoration
        return trashed_item.workflow.get_graph().get_position(trashed_item)

    def trash(
        self,
        item_to_trash: AutomationActionNode,
        requesting_user: AbstractUser,
        trash_entry: TrashEntry,
    ):
        super().trash(item_to_trash, requesting_user, trash_entry)

        if (
            trash_entry.trash_operation_type
            != ReplaceAutomationNodeTrashOperationType.type
        ):
            item_to_trash.workflow.get_graph().remove(item_to_trash)
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
        workflow = trashed_item.workflow

        super().restore(trashed_item, trash_entry)

        AutomationNodeHandler().invalidate_node_cache(trashed_item.workflow)

        if (
            trash_entry.trash_operation_type
            != ReplaceAutomationNodeTrashOperationType.type
        ):
            (
                reference_node_id,
                position,
                output,
            ) = trash_entry.additional_restoration_data

            try:
                reference_node = (
                    AutomationNodeHandler().get_node(reference_node_id)
                    if reference_node_id
                    else None
                )
            except AutomationNodeDoesNotExist as exc:
                raise TrashItemRestorationDisallowed(
                    "This automation node cannot be "
                    "restored as its reference node has been deleted."
                ) from exc

            # Does the output still exists?
            if (
                reference_node is not None
                and output
                not in reference_node.service.get_type().get_edges(
                    reference_node.service.specific
                )
            ):
                raise TrashItemRestorationDisallowed(
                    "This automation node cannot be "
                    "restored as its branch has been deleted."
                )

            workflow.get_graph().insert(trashed_item, reference_node, position, output)

            automation_node_created.send(self, node=trashed_item, user=None)
            automation_workflow_updated.send(self, workflow=workflow, user=None)

    def permanently_delete_item(
        self, trashed_item: AutomationNode, trash_item_lookup_cache=None
    ):
        trashed_item.delete()

    def get_restore_operation_type(self) -> str:
        return RestoreAutomationNodeOperationType.type
