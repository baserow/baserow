from typing import Dict, List

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationNodeResult,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.automation.workflows.operations import (
    ReadAutomationWorkflowOperationType,
)
from baserow.core.handler import CoreHandler


class AutomationHistoryService:
    def __init__(self):
        self.handler = AutomationHistoryHandler()
        self.workflow_handler = AutomationWorkflowHandler()

    def _check_workflow_permissions(
        self, user: AbstractUser, workflow: AutomationWorkflow
    ) -> None:
        CoreHandler().check_permissions(
            user,
            ReadAutomationWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

    def get_workflow_histories(
        self, user: AbstractUser, workflow_id: int
    ) -> QuerySet[AutomationWorkflowHistory]:
        workflow = self.workflow_handler.get_workflow(workflow_id)
        self._check_workflow_permissions(user, workflow)
        return self.handler.get_workflow_histories(workflow)

    def get_node_histories(
        self, user: AbstractUser, workflow_history_id: int
    ) -> List[AutomationNodeHistory]:
        workflow_history = self.handler.get_workflow_history(workflow_history_id)
        workflow = workflow_history.original_workflow
        self._check_workflow_permissions(user, workflow)
        return list(self.handler.get_node_histories(workflow_history))

    def get_node_history_result(
        self, user: AbstractUser, node_history_id: int
    ) -> AutomationNodeResult:
        node_history = self.handler.get_node_history(node_history_id)
        workflow = node_history.workflow_history.original_workflow
        self._check_workflow_permissions(user, workflow)
        return self.handler.get_node_history_result(node_history)

    def get_edge_labels(
        self,
        user: AbstractUser,
        node_histories: List[AutomationNodeHistory],
    ) -> Dict[int, str]:
        if not node_histories:
            return {}

        workflow = node_histories[0].workflow_history.original_workflow
        self._check_workflow_permissions(user, workflow)
        return self.handler.get_edge_labels(node_histories)
