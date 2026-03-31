from datetime import datetime
from typing import Dict, List, Optional, Union

from django.db.models import QuerySet

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.exceptions import (
    AutomationWorkflowHistoryDoesNotExist,
    AutomationWorkflowHistoryNodeResultDoesNotExist,
)
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
    AutomationNodeResult,
    AutomationWorkflowHistory,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.workflows.models import AutomationWorkflow


class AutomationHistoryHandler:
    def get_workflow_histories(
        self, workflow: AutomationWorkflow, base_queryset: Optional[QuerySet] = None
    ) -> QuerySet[AutomationWorkflowHistory]:
        """
        Returns all the AutomationWorkflowHistory related to the provided workflow.

        Excludes any simulation histories that haven't yet been deleted.
        """

        if base_queryset is None:
            base_queryset = AutomationWorkflowHistory.objects.all()

        return base_queryset.filter(
            workflow=workflow,
            simulate_until_node__isnull=True,
        ).prefetch_related("workflow__automation__workspace")

    def get_workflow_history(
        self, history_id: int, base_queryset: Optional[QuerySet] = None
    ) -> AutomationWorkflowHistory:
        """
        Returns a AutomationWorkflowHistory by its ID.

        :param history_id: The ID of the AutomationWorkflowHistory.
        :param base_queryset: Can be provided to already filter or apply performance
            improvements to the queryset when it's being executed.
        :raises AutomationWorkflowHistoryDoesNotExist: If the history doesn't exist.
        :return: The model instance of the AutomationWorkflowHistory
        """

        if base_queryset is None:
            base_queryset = AutomationWorkflowHistory.objects.all()

        try:
            return base_queryset.select_related("workflow__automation__workspace").get(
                id=history_id
            )
        except AutomationWorkflowHistory.DoesNotExist:
            raise AutomationWorkflowHistoryDoesNotExist(history_id)

    def create_workflow_history(
        self,
        workflow: AutomationWorkflow,
        started_on: datetime,
        is_test_run: bool,
        event_payload: Optional[Union[Dict, List[Dict]]] = None,
        simulate_until_node: Optional[AutomationNode] = None,
        status: HistoryStatusChoices = HistoryStatusChoices.STARTED,
        completed_on: Optional[datetime] = None,
        message: str = "",
    ) -> AutomationWorkflowHistory:
        """Creates a history entry for a Workflow run."""

        return AutomationWorkflowHistory.objects.create(
            workflow=workflow,
            started_on=started_on,
            is_test_run=is_test_run,
            simulate_until_node=simulate_until_node,
            event_payload=event_payload,
            status=status,
            completed_on=completed_on,
            message=message,
        )

    def create_node_history(
        self,
        workflow_history: AutomationWorkflowHistory,
        node: AutomationNode,
        started_on: datetime,
        status: HistoryStatusChoices = HistoryStatusChoices.STARTED,
        completed_on: Optional[datetime] = None,
        message: str = "",
    ) -> AutomationNodeHistory:
        """Creates a history entry for a Node dispatch."""

        return AutomationNodeHistory.objects.create(
            workflow_history=workflow_history,
            node=node,
            started_on=started_on,
            status=status,
            completed_on=completed_on,
            message=message,
        )

    def create_node_result(
        self,
        node_history: AutomationNodeHistory,
        result: Optional[Union[Dict, List[Dict]]] = None,
        iteration_path: str = "",
    ) -> AutomationNodeResult:
        """Saves the result of a Node dispatch."""

        result = result if result else {}
        return AutomationNodeResult.objects.create(
            node_history=node_history,
            iteration_path=iteration_path,
            result=result,
        )

    def get_node_result(self, history, node, iteration_path):
        """
        Returns the result for the given history/node/iteration_path.
        """

        try:
            node_result = AutomationNodeResult.objects.only("result").get(
                node_history__workflow_history_id=history.id,
                node_history__node_id=node.id,
                iteration_path=iteration_path,
            )
        except AutomationNodeResult.DoesNotExist:
            raise AutomationWorkflowHistoryNodeResultDoesNotExist()

        return node_result.result
