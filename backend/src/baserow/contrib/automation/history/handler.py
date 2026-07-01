from datetime import datetime
from typing import Dict, List, Optional, Union

from django.db.models import Prefetch, QuerySet

from baserow.contrib.automation.history.constants import HistoryStatusChoices
from baserow.contrib.automation.history.exceptions import (
    AutomationNodeHistoryDoesNotExist,
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
            original_workflow=workflow,
            simulate_until_node__isnull=True,
        )

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
        original_workflow: AutomationWorkflow,
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
            original_workflow=original_workflow,
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

    def get_node_history(
        self,
        node_history_id: int,
        base_queryset: Optional[QuerySet] = None,
    ) -> AutomationNodeHistory:
        """Returns an AutomationNodeHistory by its ID."""

        if base_queryset is None:
            base_queryset = AutomationNodeHistory.objects.all()

        try:
            return base_queryset.select_related(
                "workflow_history__original_workflow__automation__workspace",
            ).get(id=node_history_id)
        except AutomationNodeHistory.DoesNotExist:
            raise AutomationNodeHistoryDoesNotExist(node_history_id)

    def get_node_histories(
        self, workflow_history: AutomationWorkflowHistory
    ) -> QuerySet[AutomationNodeHistory]:
        """Returns a queryset of AutomationNodeHistory by the workflow history."""

        return (
            AutomationNodeHistory.objects.filter(workflow_history=workflow_history)
            .select_related("node", "node__workflow")
            .prefetch_related(
                Prefetch(
                    "node_results",
                    queryset=AutomationNodeResult.objects.only(
                        "id", "node_history_id", "iteration_path"
                    ),
                )
            )
            .order_by("started_on", "id")
        )

    def get_node_history_result(
        self, node_history: AutomationNodeHistory
    ) -> AutomationNodeResult:
        """Returns the AutomationNodeResult for the given node history."""

        try:
            return AutomationNodeResult.objects.only("result").get(
                node_history=node_history
            )
        except AutomationNodeResult.DoesNotExist:
            raise AutomationWorkflowHistoryNodeResultDoesNotExist()

    def get_edge_labels(
        self, node_histories: List[AutomationNodeHistory]
    ) -> Dict[int, str]:
        """
        For each node history whose result has an edge label, return a
        mapping of `node_history_id -> label` of the edge taken.
        """

        if not node_histories:
            return {}

        results = AutomationNodeResult.objects.filter(
            node_history_id__in=[nh.id for nh in node_histories],
        ).only("node_history_id", "result")

        return {
            nr.node_history_id: label
            for nr in results
            if (label := nr.result.get("edge", {}).get("label"))
        }
