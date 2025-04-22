from typing import List

from django.contrib.auth.models import AbstractUser

from baserow.core.handler import CoreHandler
from baserow.contrib.automation.nodes.node_types import AutomationNodeType
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.operations import (
    ListAutomationNodeOperationType,
    CreateAutomationNodeOperationType,
    UpdateAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.signals import (
    automation_node_created,
    automation_node_updated,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.nodes.types import UpdatedAutomationNode


class AutomationNodeService:
    def __init__(self):
        self.handler = AutomationNodeHandler()

    def create_node(
        self,
        user: AbstractUser,
        node_type: AutomationNodeType,
        workflow: AutomationWorkflow,
        **kwargs,
    ) -> AutomationNode:
        """
        Creates a new automation node for a workflow given the user permissions.

        :param user: The user trying to create the automation node.
        :param node_type: The type of the automation node.
        :param workflow: The workflow the automation node is associated with.
        :param kwargs: Additional attributes of the automation node.
        :return: The created automation node.
        """

        CoreHandler().check_permissions(
            user,
            CreateAutomationNodeOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        prepared_values = node_type.prepare_values(kwargs, user)

        new_node = self.handler.create_node(
            node_type, workflow=workflow, **prepared_values
        )

        automation_node_created.send(
            self,
            automation_node=new_node,
            user=user,
        )

        return new_node

    def get_nodes(
        self,
        user: AbstractUser,
        workflow: AutomationWorkflow,
    ) -> List[AutomationNode]:
        """
        Returns all the automation nodes for a specific workflow that can be
        accessed by the user.

        :param user: The user trying to get the workflow_actions.
        :param workflow: The workflow the automation node is associated with.
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
            workflow, base_queryset=user_nodes
        )

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

        updated_node = self.handler.update_node(node, **kwargs)
        automation_node_updated.send(
            self, user=user, node=updated_node.node
        )

        return updated_node