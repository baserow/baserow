from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.nodes.operations import ReadAutomationNodeOperationType
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.operations import (
    ReadAutomationWorkflowOperationType,
)
from baserow.core.handler import CoreHandler


class AutomationHistoryService:
    def __init__(self):
        self.handler = AutomationHistoryHandler()
        self.workflow_handler = AutomationWorkflowHandler()

    def get_workflow_history(
        self, user: AbstractUser, workflow_id: int
    ) -> QuerySet[AutomationWorkflowHistory]:
        """
        Returns an AutomationWorkflowHistory queryset related to a workflow.

        :param user: The user requesting the workflow history.
        :param workflow_id: The ID of the workflow.
        :return: A queryset of workflow histories.
        """

        workflow = self.workflow_handler.get_workflow(workflow_id)

        CoreHandler().check_permissions(
            user,
            ReadAutomationWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        return self.handler.get_workflow_history(workflow)

    def get_node_history(
        self, user: AbstractUser, node_id: int
    ) -> QuerySet[AutomationNodeHistory]:
        """
        Returns an AutomationNodeHistory queryset related to a node.

        :param user: The user requesting the node history.
        :param node_id: The ID of the node.
        :return: A queryset of node histories.
        """

        node = self.node_handler.get_node(node_id)

        CoreHandler().check_permissions(
            user,
            ReadAutomationNodeOperationType.type,
            workspace=node.workflow.automation.workspace,
            context=node,
        )

        return self.handler.get_node_history(node)
