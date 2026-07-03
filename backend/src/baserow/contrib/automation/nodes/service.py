from typing import Iterable, Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
    AutomationNodeMissingOutput,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import (
    AutomationNodeType,
    CoreGotoActionNodeType,
)
from baserow.contrib.automation.nodes.operations import (
    CreateAutomationNodeOperationType,
    DeleteAutomationNodeOperationType,
    DuplicateAutomationNodeOperationType,
    ListAutomationNodeOperationType,
    ReadAutomationNodeOperationType,
    UpdateAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.registries import (
    ReplaceAutomationNodeTrashOperationType,
    automation_node_type_registry,
)
from baserow.contrib.automation.nodes.signals import (
    automation_node_created,
    automation_node_deleted,
    automation_node_updated,
)
from baserow.contrib.automation.nodes.types import (
    AutomationNodeMove,
    ReplacedAutomationNode,
    UpdatedAutomationNode,
)
from baserow.contrib.automation.workflows.constants import WORKFLOW_DIRTY_CACHE_KEY
from baserow.contrib.automation.workflows.signals import automation_workflow_updated
from baserow.contrib.integrations.core.models import CoreGotoService
from baserow.core.cache import global_cache
from baserow.core.graph.exceptions import GraphPointReferencePointInvalid
from baserow.core.graph.types import GraphPointPositionType
from baserow.core.handler import CoreHandler
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.trash.handler import TrashHandler


class AutomationNodeService:
    def __init__(self):
        self.handler = AutomationNodeHandler()

    def get_node(self, user: AbstractUser, node_id: int) -> AutomationNode:
        """
        Returns an AutomationNode instance by its ID.

        :param user: The user trying to get the workflow_actions.
        :param node_id: The ID of the node.
        :return: The node instance.
        """

        node = self.handler.get_node(node_id)

        CoreHandler().check_permissions(
            user,
            ReadAutomationNodeOperationType.type,
            workspace=node.workflow.automation.workspace,
            context=node,
        )

        return node

    def get_nodes(
        self,
        user: AbstractUser,
        workflow: AutomationWorkflow,
        specific: Optional[bool] = True,
    ) -> Iterable[AutomationNode]:
        """
        Returns all the automation nodes for a specific workflow that can be
        accessed by the user.

        :param user: The user trying to get the workflow_actions.
        :param workflow: The workflow the automation node is associated with.
        :param specific: If True, returns the specific node type.
        :return: The automation nodes of the workflow.
        """

        CoreHandler().check_permissions(
            user,
            ListAutomationNodeOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        user_nodes = CoreHandler().filter_queryset(
            user,
            ListAutomationNodeOperationType.type,
            AutomationNode.objects.all(),
            workspace=workflow.automation.workspace,
        )

        return self.handler.get_nodes(
            workflow, specific=specific, base_queryset=user_nodes
        )

    def _check_position(
        self,
        workflow: AutomationWorkflow,
        reference_node: AutomationNode | None,
        position: GraphPointPositionType,
        output: str,
    ):
        """
        Validates the position.
        """

        if reference_node is None:
            return

        if reference_node.workflow_id != workflow.id:
            raise GraphPointReferencePointInvalid(
                f"The reference node {reference_node.id} doesn't exist"
            )

        if output not in reference_node.service.get_type().get_edges(
            reference_node.service.specific
        ):
            raise AutomationNodeMissingOutput(
                f"Output {output} doesn't exist on node {reference_node.id}"
            )

        if position == "child" and not reference_node.get_type().is_container:
            raise GraphPointReferencePointInvalid(
                f"The reference node {reference_node.id} can't have child"
            )

    def create_node(
        self,
        user: AbstractUser,
        node_type: AutomationNodeType,
        workflow: AutomationWorkflow,
        reference_node_id: int | None = None,
        position: GraphPointPositionType = "south",  # south, child
        output: str = "",
        **kwargs,
    ) -> AutomationNode:
        """
        Creates a new automation node for a workflow given the user permissions.

        :param user: The user trying to create the automation node.
        :param node_type: The type of the automation node.
        :param workflow: The workflow the automation node is associated with.
        :param reference_node_id: The node reference node for the position.
        :param position: The position relative to the reference node.
        :param output: The output of the reference node.
        :param kwargs: Additional attributes of the automation node.
        :return: The created automation node.
        """

        CoreHandler().check_permissions(
            user,
            CreateAutomationNodeOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        node_type.raise_if_deactivated(workflow.automation.workspace)

        try:
            reference_node = (
                self.handler.get_node(reference_node_id) if reference_node_id else None
            )
        except AutomationNodeDoesNotExist as e:
            raise GraphPointReferencePointInvalid(
                f"The reference node {reference_node_id} doesn't exist"
            ) from e

        self._check_position(workflow, reference_node, position, output)

        node_type.before_create(workflow, reference_node, position, output)

        prepared_values = node_type.prepare_values(
            {**kwargs, "workflow": workflow},
            user,
        )

        # Preselect first integration if exactly one exists
        if node_type.get_service_type().integration_type:
            integrations_of_type = [
                i
                for i in IntegrationHandler().get_integrations(workflow.automation)
                if i.get_type().type == node_type.get_service_type().integration_type
            ]

            if len(integrations_of_type) == 1:
                prepared_values["service"].integration = integrations_of_type[0]
                prepared_values["service"].save()

        new_node = self.handler.create_node(
            node_type,
            **prepared_values,
        )

        node_type.after_create(new_node)

        workflow.get_graph().insert(new_node, reference_node, position, output)

        cache_key = WORKFLOW_DIRTY_CACHE_KEY.format(workflow.id)
        global_cache.update(cache_key, lambda _: True)

        automation_node_created.send(
            self,
            node=new_node,
            user=user,
        )

        automation_workflow_updated.send(self, workflow=workflow, user=user)

        return new_node

    def update_node(
        self,
        user: AbstractUser,
        node_id: int,
        **kwargs,
    ) -> UpdatedAutomationNode:
        """
        Updates fields of a node.

        :param user: The user trying to update the node.
        :param node_id: The node that should be updated.
        :param kwargs: The fields that should be updated with their corresponding value
        :return: UpdatedAutomationNode.
        """

        node = self.handler.get_node(node_id)
        node_type = node.get_type()

        CoreHandler().check_permissions(
            user,
            UpdateAutomationNodeOperationType.type,
            workspace=node.workflow.automation.workspace,
            context=node,
        )

        node_type.raise_if_deactivated(node.workflow.automation.workspace)

        # Export the 'original' node values now, as `prepare_values`
        # will be changing the service first, and then `update_node`
        # will be change the node itself.
        original_node_values = node_type.export_prepared_values(node)

        # Prepare the node's values, which handles service updates too.
        prepared_values = node_type.prepare_values(kwargs, user, node)

        # Update the node itself.
        updated_node = self.handler.update_node(node, **prepared_values)

        # Now export the 'new' node values, since everything has been updated.
        new_node_values = node_type.export_prepared_values(node)

        cache_key = WORKFLOW_DIRTY_CACHE_KEY.format(node.workflow.id)
        global_cache.update(cache_key, lambda _: True)

        automation_node_updated.send(self, user=user, node=updated_node)

        return UpdatedAutomationNode(
            node=updated_node,
            original_values=original_node_values,
            new_values=new_node_values,
        )

    def delete_node(
        self, user: AbstractUser | None, node_id: int, ignore_user_for_signal=False
    ) -> AutomationNode:
        """
        Deletes the specified automation node.

        :param user: The user trying to delete the node.
        :param node_id: The ID of the node to delete.
        :return: The deleted node.
        """

        node = self.handler.get_node(node_id)
        workflow = node.workflow

        CoreHandler().check_permissions(
            user,
            DeleteAutomationNodeOperationType.type,
            workspace=node.workflow.automation.workspace,
            context=node,
        )

        automation = workflow.automation

        node.get_type().before_delete(node.specific)

        TrashHandler.trash(
            user if not ignore_user_for_signal else None,
            automation.workspace,
            automation,
            node,
        )

        cache_key = WORKFLOW_DIRTY_CACHE_KEY.format(workflow.id)
        global_cache.update(cache_key, lambda _: True)

        automation_node_deleted.send(
            self,
            workflow=workflow,
            node_id=node.id,
            user=user if not ignore_user_for_signal else None,
        )

        return node

    def duplicate_node(
        self,
        user: AbstractUser,
        source_node_id: AutomationNode,
    ) -> AutomationNode:
        """
        Duplicates an existing AutomationNode instance.

        :param user: The user initiating the duplication.
        :param source_node_id: The id of the node that is being duplicated.
        :raises ValueError: When the provided node is not an instance of
            AutomationNode.
        :return: The duplicated node.
        """

        source_node = AutomationNodeService().get_node(user, source_node_id)
        workflow = source_node.workflow

        CoreHandler().check_permissions(
            user,
            DuplicateAutomationNodeOperationType.type,
            workspace=workflow.automation.workspace,
            context=source_node,
        )

        source_node.get_type().before_create(workflow, source_node, "south", "")

        source_node.get_type().raise_if_deactivated(workflow.automation.workspace)

        duplicated_node = self.handler.duplicate_node(source_node)

        workflow.get_graph().insert(duplicated_node, source_node, "south", "")

        cache_key = WORKFLOW_DIRTY_CACHE_KEY.format(workflow.id)
        global_cache.update(cache_key, lambda _: True)

        automation_node_created.send(
            self,
            node=duplicated_node,
            user=user,
        )
        automation_workflow_updated.send(self, workflow=workflow, user=user)

        return duplicated_node

    def replace_node(
        self,
        user: AbstractUser,
        node_id: int,
        new_node_type_str: str,
        existing_node: AutomationNode | None = None,
    ) -> ReplacedAutomationNode:
        """
        Replaces an existing automation node with a new one of a different type.

        :param user: The user trying to replace the node.
        :param node_id: The ID of the node to replace.
        :param new_node_type_str: The type of the new node to replace with.
        :param existing_node: If provided, used to replace the node instead of creating
          a new instance. Used during undo/redo.
        :return: The replaced automation node.
        """

        node_to_replace = self.get_node(user, node_id)
        workflow = node_to_replace.workflow
        automation = workflow.automation

        node_type: AutomationNodeType = node_to_replace.get_type()

        CoreHandler().check_permissions(
            user,
            CreateAutomationNodeOperationType.type,
            workspace=node_to_replace.workflow.automation.workspace,
            context=node_to_replace.workflow,
        )

        if not existing_node:
            new_node_type = automation_node_type_registry.get(new_node_type_str)
            new_node_type.raise_if_deactivated(automation.workspace)
            node_type.before_replace(node_to_replace, new_node_type)

            prepared_values = new_node_type.prepare_values({}, user)

            new_node = self.handler.create_node(
                new_node_type,
                workflow=workflow,
                **prepared_values,
            )

            new_node_type.after_create(new_node)

        else:
            new_node = existing_node

        automation_node_created.send(
            self,
            node=new_node,
            user=user,
        )

        # When we use a replace operation type, we make sure no graph modification is
        # made so that we can do it here.
        TrashHandler.trash(
            user,
            automation.workspace,
            automation,
            node_to_replace,
            trash_operation_type=ReplaceAutomationNodeTrashOperationType.type,
        )

        workflow.get_graph().replace(node_to_replace, new_node)

        if workflow.simulate_until_node_id == node_to_replace.id:
            workflow.simulate_until_node = None
            workflow.save(update_fields=["simulate_until_node"])

        cache_key = WORKFLOW_DIRTY_CACHE_KEY.format(workflow.id)
        global_cache.update(cache_key, lambda _: True)

        automation_node_deleted.send(
            self,
            workflow=workflow,
            node_id=node_to_replace.id,
            user=user,
        )

        automation_workflow_updated.send(self, workflow=workflow, user=user)

        return ReplacedAutomationNode(
            node=new_node,
            original_node_id=node_to_replace.id,
            original_node_type=node_type.type,
        )

    def move_node(
        self,
        user: AbstractUser,
        node_id_to_move: int,
        reference_node_id: int | None,
        position: GraphPointPositionType,
        output: str,
    ) -> AutomationNodeMove:
        """
        Moves an existing automation node to a new position in the workflow.

        :param user: The user trying to move the node.
        :param node_id_to_move: The ID of the node to move.
        :param reference_node_id: The node the new position is relative to.
        :param position: The new position relative to the reference node.
        :param output: The new output of the reference node.
        :raises AutomationNodeNotMovable: If the node cannot be moved.
        :return: The move operation details.
        """

        node_to_move = self.get_node(user, node_id_to_move)
        node_type: AutomationNodeType = node_to_move.get_type()

        workflow = node_to_move.workflow

        CoreHandler().check_permissions(
            user,
            UpdateAutomationNodeOperationType.type,
            workspace=node_to_move.workflow.automation.workspace,
            context=node_to_move,
        )
        try:
            reference_node = (
                self.handler.get_node(reference_node_id) if reference_node_id else None
            )
        except AutomationNodeDoesNotExist as e:
            raise GraphPointReferencePointInvalid(
                f"The reference node {reference_node_id} doesn't exist"
            ) from e

        self._check_position(workflow, reference_node, position, output)

        if reference_node.id == node_to_move.id:
            raise GraphPointReferencePointInvalid(
                "The reference node and the moved node must be different"
            )

        node_type.before_move(node_to_move, reference_node, position, output)

        # We extract the current node position to restore it if we undo the operation.
        [
            previous_reference_node_id,
            previous_position,
            previous_output,
        ] = workflow.get_graph().get_position(node_to_move)

        previous_reference_node = (
            self.get_node(user, previous_reference_node_id)
            if previous_reference_node_id
            else None
        )

        workflow.get_graph().move(node_to_move, reference_node, position, output)

        # A move can change a node's level, which may invalidate a "Go to node"
        # link that targets - or originates from - the moved node (or one of its
        # descendants). Clear any such now-cross-level links so the editor and
        # the runtime agree on what the workflow does.
        cleared_goto_links = self._clear_invalidated_goto_links(user, workflow)

        cache_key = WORKFLOW_DIRTY_CACHE_KEY.format(workflow.id)
        global_cache.update(cache_key, lambda _: True)

        automation_workflow_updated.send(self, workflow=workflow, user=user)

        return AutomationNodeMove(
            node=node_to_move,
            previous_reference_node=previous_reference_node,
            previous_position=previous_position,
            previous_output=previous_output,
            cleared_goto_links=cleared_goto_links,
        )

    def _clear_invalidated_goto_links(
        self,
        user: AbstractUser,
        workflow: AutomationWorkflow,
    ) -> list[tuple[int, int]]:
        """
        Nulls every "Go to node" destination in the workflow that is no longer at
        the same level as its source node. Intended to be called after a move,
        which can change a node's level. We simply re-validate every goto link in
        the workflow: there are few of them, and this avoids depending on the
        exact descendant semantics of the graph to work out which links the move
        could have touched. A link survives when source and destination still
        share a level (e.g. both moved together inside a container).

        An `automation_node_updated` signal is sent for each cleared Go to node
        so connected clients drop the stale link.

        :return: A list of (goto_node_id, previous_destination_node_id) tuples
            describing the links that were cleared, so the caller can restore
            them when a move is undone.
        """

        goto_services = CoreGotoService.objects.filter(
            automation_workflow_node__workflow=workflow,
            destination_node__isnull=False,
        ).select_related("automation_workflow_node", "destination_node")

        cleared_goto_links: list[tuple[int, int]] = []
        for service in goto_services:
            source_node = service.automation_workflow_node
            destination_node = service.destination_node
            if (
                CoreGotoActionNodeType.validate_goto_destination(
                    source_node, destination_node
                )
                is None
            ):
                continue

            previous_destination_id = service.destination_node_id
            service.destination_node = None
            service.save(update_fields=["destination_node"])
            cleared_goto_links.append((source_node.id, previous_destination_id))

            automation_node_updated.send(
                self, user=user, node=self.handler.get_node(source_node.id)
            )

        return cleared_goto_links

    def restore_goto_links(
        self,
        user: AbstractUser,
        links: list[tuple[int, int]],
    ) -> None:
        """
        Re-applies "Go to node" destinations that a move cleared, used when that
        move is undone. Each link is re-validated against the (restored) graph
        and skipped if it would still be invalid, so we never persist a
        cross-level link.

        :param links: (goto_node_id, destination_node_id) tuples to restore.
        """

        for goto_node_id, destination_node_id in links:
            try:
                goto_node = self.handler.get_node(goto_node_id)
                destination_node = self.handler.get_node(destination_node_id)
            except AutomationNodeDoesNotExist:
                # An endpoint was deleted after the move was made; nothing to
                # restore. (The link stays cleared, which is correct.)
                continue
            if (
                CoreGotoActionNodeType.validate_goto_destination(
                    goto_node, destination_node
                )
                is not None
            ):
                continue

            service = goto_node.service.specific
            service.destination_node = destination_node
            service.save(update_fields=["destination_node"])

            automation_node_updated.send(
                self, user=user, node=self.handler.get_node(goto_node_id)
            )
