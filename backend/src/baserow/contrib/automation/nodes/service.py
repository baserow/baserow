from typing import List

from django.contrib.auth.models import AbstractUser

from baserow.core.handler import CoreHandler
from baserow.contrib.automation.nodes.node_types import AutomationNodeType
from baserow.contrib.automation.models import AutomationWorkflow
from baserow.contrib.automation.nodes.operations import (
    ListAutomationWorkflowNodeOperationType,
    CreateAutomationNodeOperationType,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.signals import automation_node_created
from baserow.contrib.automation.nodes.models import AutomationNode


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
            ListAutomationWorkflowNodeOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        user_nodes = CoreHandler().filter_queryset(
            user,
            ListAutomationWorkflowNodeOperationType.type,
            AutomationNode.objects.all(),
            workspace=workflow.automation.workspace,
        )

        return self.handler.get_nodes(
            workflow, base_queryset=user_nodes
        )
