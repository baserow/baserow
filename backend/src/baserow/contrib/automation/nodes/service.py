from typing import Iterable, List, Optional

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeBeforeInvalid,
    AutomationNodeTypeNotReplaceable,
    AutomationTriggerModificationDisallowed,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.node_types import (
    AutomationNodeTriggerType,
    AutomationNodeType,
)
from baserow.contrib.automation.nodes.operations import (
    CreateAutomationNodeOperationType,
    DeleteAutomationNodeOperationType,
    DuplicateAutomationNodeOperationType,
    ListAutomationNodeOperationType,
    OrderAutomationNodeOperationType,
    ReadAutomationNodeOperationType,
    UpdateAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.signals import (
    automation_node_created,
    automation_node_deleted,
    automation_node_updated,
    automation_nodes_reordered,
)
from baserow.contrib.automation.nodes.types import (
    ReplacedAutomationNode,
    UpdatedAutomationNode,
)
from baserow.core.handler import CoreHandler


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

    def create_node(
        self,
        user: AbstractUser,
        node_type: AutomationNodeType,
        workflow: AutomationWorkflow,
        before: Optional[AutomationNode] = None,
        order: Optional[str] = None,
        **kwargs,
    ) -> AutomationNode:
        """
        Creates a new automation node for a workflow given the user permissions.

        :param user: The user trying to create the automation node.
        :param node_type: The type of the automation node.
        :param workflow: The workflow the automation node is associated with.
        :param before: If set, the new node is inserted before this node.
        :param order: The order of the new node. If not set, it will be determined
            automatically based on the existing nodes in the workflow.
        :param kwargs: Additional attributes of the automation node.
        :raises AutomationTriggerModificationDisallowed: If the node_type is a trigger.
        :return: The created automation node.
        """

        # Triggers are not directly created by users. When a workflow is created,
        # the trigger node is created automatically, so users are only able to change
        # the trigger node type, not create a new one.
        if node_type.is_workflow_trigger:
            raise AutomationTriggerModificationDisallowed()

        CoreHandler().check_permissions(
            user,
            CreateAutomationNodeOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        # If we've been given a `before` node, validate it.
        if before:
            if workflow.id != before.workflow_id:
                raise AutomationNodeBeforeInvalid(
                    "The `before` node must belong to the same workflow "
                    "as the one supplied."
                )
            # TODO: replace with a `before.get_type().is_trigger` check.
            if isinstance(before.get_type(), AutomationNodeTriggerType):
                # You can't create a node before a trigger node. Even if `node_type` is
                # a trigger, API consumers must delete `before` and then try again.
                raise AutomationNodeBeforeInvalid(
                    "You cannot create an automation node before a trigger."
                )

        prepared_values = node_type.prepare_values(kwargs, user)

        new_node = self.handler.create_node(
            node_type, order=order, workflow=workflow, before=before, **prepared_values
        )

        automation_node_created.send(
            self,
            node=new_node,
            user=user,
        )

        return new_node

    def update_node(
        self, user: AbstractUser, node_id: int, **kwargs
    ) -> UpdatedAutomationNode:
        """
        Updates fields of a node.

        :param user: The user trying to update the node.
        :param node_id: The node that should be updated.
        :param kwargs: The fields that should be updated with their corresponding value
        :return: The updated workflow.
        """

        node = self.handler.get_node(node_id)

        CoreHandler().check_permissions(
            user,
            UpdateAutomationNodeOperationType.type,
            workspace=node.workflow.automation.workspace,
            context=node,
        )

        prepared_values = node.get_type().prepare_values(kwargs, user, node)
        updated_node = self.handler.update_node(node, **prepared_values)

        automation_node_updated.send(self, user=user, node=updated_node.node)

        return updated_node

    def delete_node(self, user: AbstractUser, node_id: int) -> AutomationNode:
        """
        Deletes the specified automation node.

        :param user: The user trying to delete the node.
        :param node_id: The ID of the node to delete.
        :raises AutomationTriggerModificationDisallowed: If the node is a trigger.
        """

        node = self.handler.get_node(node_id)

        # If we received a trigger node, we cannot delete it.
        if node.get_type().is_workflow_trigger:
            raise AutomationTriggerModificationDisallowed()

        CoreHandler().check_permissions(
            user,
            DeleteAutomationNodeOperationType.type,
            workspace=node.workflow.automation.workspace,
            context=node,
        )

        self.handler.delete_node(user, node)

        automation_node_deleted.send(
            self,
            workflow=node.workflow,
            node_id=node.id,
            user=user,
        )

        return node

    def order_nodes(
        self, user: AbstractUser, workflow: AutomationWorkflow, order: List[int]
    ) -> List[int]:
        """
        Assigns a new order to the nodes in a workflow.

        :param user: The user trying to order the workflows.
        :param workflow The workflow that the nodes belong to.
        :param order: The new order of the nodes.
        :return: The new order of the nodes.
        """

        automation = workflow.automation
        CoreHandler().check_permissions(
            user,
            OrderAutomationNodeOperationType.type,
            workspace=automation.workspace,
            context=workflow,
        )

        all_nodes = self.handler.get_nodes(
            workflow, specific=False, base_queryset=AutomationNode.objects
        )

        user_nodes = CoreHandler().filter_queryset(
            user,
            OrderAutomationNodeOperationType.type,
            all_nodes,
            workspace=automation.workspace,
        )

        new_order = self.handler.order_nodes(workflow, order, user_nodes)

        automation_nodes_reordered.send(
            self, workflow=workflow, order=new_order, user=user
        )

        return new_order

    def duplicate_node(
        self,
        user: AbstractUser,
        node: AutomationNode,
    ) -> AutomationNode:
        """
        Duplicates an existing AutomationNode instance.

        :param user: The user initiating the duplication.
        :param node: The node that is being duplicated.
        :raises ValueError: When the provided node is not an instance of
            AutomationNode.
        :raises AutomationTriggerModificationDisallowed: If the node is a trigger.
        :return: The duplicated node.
        """

        CoreHandler().check_permissions(
            user,
            DuplicateAutomationNodeOperationType.type,
            workspace=node.workflow.automation.workspace,
            context=node,
        )

        # If we received a trigger node, we cannot duplicate it.
        if node.get_type().is_workflow_trigger:
            raise AutomationTriggerModificationDisallowed()

        node_clone = self.handler.duplicate_node(node)

        automation_node_created.send(
            self,
            node=node_clone,
            user=user,
        )

        return node_clone

    def replace_node(
        self, user: AbstractUser, node_id: int, new_node_type_str: str, **kwargs
    ) -> ReplacedAutomationNode:
        """
        Replaces an existing automation node with a new one of a different type.

        :param user: The user trying to replace the node.
        :param node_id: The ID of the node to replace.
        :param new_node_type_str: The type of the new node to replace with.
        :raises AutomationNodeTypeNotReplaceable when the node type cannot be replaced
        :return: The replaced automation node.
        """

        node = self.get_node(user, node_id)
        node_type: AutomationNodeType = node.get_type()
        new_node_type = automation_node_type_registry.get(new_node_type_str)

        # If they tried to update a trigger with an action
        # or vice versa, raise an error.
        if not node_type.is_replaceable_with(new_node_type):
            raise AutomationNodeTypeNotReplaceable()

        CoreHandler().check_permissions(
            user,
            CreateAutomationNodeOperationType.type,
            workspace=node.workflow.automation.workspace,
            context=node.workflow,
        )

        return self.handler.replace_node(
            user,
            node,
            new_node_type,
            order=node.order,
            previous_node_id=node.previous_node_id,
        )
