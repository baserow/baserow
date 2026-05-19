from typing import Dict, Optional, Set, Tuple

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationNodeResult,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.workflows.operations import (
    ReadAutomationWorkflowOperationType,
)
from baserow.core.handler import CoreHandler


class AutomationHistoryService:
    def __init__(self):
        self.handler = AutomationHistoryHandler()
        self.workflow_handler = AutomationWorkflowHandler()

    def get_workflow_histories(
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

        return self.handler.get_workflow_histories(workflow)

    def _check_workflow_history_permissions(
        self, user: AbstractUser, workflow_history: AutomationWorkflowHistory
    ) -> None:
        workflow = workflow_history.original_workflow
        CoreHandler().check_permissions(
            user,
            ReadAutomationWorkflowOperationType.type,
            workspace=workflow.automation.workspace,
            context=workflow,
        )

    def get_child_node_histories(
        self,
        user: AbstractUser,
        workflow_history_id: int,
        parent_node_id: Optional[int],
        iteration_path: str = "",
    ) -> Tuple[
        QuerySet[AutomationNodeHistory],
        Dict[int, Optional[int]],
        Set[int],
    ]:
        """
        Returns the immediate child node histories for the given history,
        optionally scoped to a parent's iteration_path.
        """

        workflow_history = self.handler.get_workflow_history(workflow_history_id)
        self._check_workflow_history_permissions(user, workflow_history)

        queryset = self.handler.get_child_node_histories(
            workflow_history, parent_node_id, iteration_path
        )
        parent_map = workflow_history.workflow.get_graph().get_parent_map()
        error_ancestor_ids = self.handler.get_error_ancestor_node_ids(workflow_history)
        return queryset, parent_map, error_ancestor_ids

    def get_node_history_result(
        self, user: AbstractUser, node_history_id: int
    ) -> AutomationNodeResult:
        """
        Returns the AutomationNodeResult for a node history.
        """

        node_history = self.handler.get_node_history(node_history_id)
        self._check_workflow_history_permissions(user, node_history.workflow_history)
        return self.handler.get_node_history_result(node_history)
