from typing import Any, Dict, List

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.contrib.automation.history.exceptions import (
    AutomationWorkflowHistoryDoesNotExist,
)
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
    UpdateAutomationWorkflowOperationType,
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

    def request_cancellation(
        self, user: AbstractUser, workflow_history_id: int
    ) -> AutomationWorkflowHistory:
        """
        Requests the cancellation of a running workflow history.

        Whoever can update the workflow can cancel its runs. Runs execute against
        the published clone, so the permission is checked against the editable
        `original_workflow`.

        :param user: The user requesting the cancellation.
        :param workflow_history_id: The id of the run to cancel.
        :raises AutomationWorkflowHistoryDoesNotExist: If the run doesn't exist or
            is a simulation run.
        :raises AutomationWorkflowHistoryNotRunning: If the run already resolved.
        :return: The refreshed workflow history.
        """

        workflow_history = self.handler.get_workflow_history(
            workflow_history_id,
            base_queryset=AutomationWorkflowHistory.objects.select_related(
                "original_workflow__automation__workspace"
            ),
        )

        if workflow_history.simulate_until_node_id is not None:
            raise AutomationWorkflowHistoryDoesNotExist(workflow_history_id)

        workflow = workflow_history.original_workflow
        CoreHandler().check_permissions(
            user,
            UpdateAutomationWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

        return self.handler.request_workflow_history_cancellation(
            workflow_history, user
        )

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

    def get_destination_labels(
        self,
        user: AbstractUser,
        node_histories: List[AutomationNodeHistory],
    ) -> Dict[int, Dict[str, Any]]:
        if not node_histories:
            return {}

        workflow = node_histories[0].workflow_history.original_workflow
        self._check_workflow_permissions(user, workflow)
        return self.handler.get_destination_labels(node_histories)
