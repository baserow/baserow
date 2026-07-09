from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Union

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
from baserow.core.db import specific_iterator
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service


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

        A node can be dispatched several times within a single run when a jump
        (e.g. the "Go to node" node) loops execution back to it. Each pass writes a
        new result with the same iteration_path, so we return the most recent one
        rather than assuming a single result exists.
        """

        node_result = (
            AutomationNodeResult.objects.only("result")
            .filter(
                node_history__workflow_history_id=history.id,
                node_history__node_id=node.id,
                iteration_path=iteration_path,
            )
            .order_by("-node_history__started_on", "-node_history_id")
            .first()
        )

        if node_result is None:
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

    def _query_node_histories(
        self, base_queryset: QuerySet[AutomationNodeHistory]
    ) -> QuerySet[AutomationNodeHistory]:
        return (
            base_queryset.select_related("node", "node__workflow")
            .prefetch_related(
                Prefetch(
                    "node_results",
                    queryset=AutomationNodeResult.objects.only(
                        "id", "node_history_id", "iteration_path"
                    ),
                )
            )
            .order_by("workflow_history_id", "started_on", "id")
        )

    def _with_specific_nodes(
        self, node_histories: QuerySet[AutomationNodeHistory]
    ) -> List[AutomationNodeHistory]:
        """
        Resolves the related nodes to their specific model instances in batches.
        """

        node_histories = list(node_histories)
        nodes = [node_history.node for node_history in node_histories]
        specific_nodes = {
            node.id: node
            for node in specific_iterator(
                nodes,
                base_model=AutomationNode,
                select_related=["workflow"],
            )
        }
        service_ids = [
            node.service_id
            for node in specific_nodes.values()
            if node.service_id is not None
        ]
        specific_services_map = {
            service.id: service
            for service in ServiceHandler().get_services(
                base_queryset=Service.objects.filter(id__in=service_ids)
            )
        }
        for node in specific_nodes.values():
            service_id = node.service_id
            if service_id is not None and service_id in specific_services_map:
                node.service = specific_services_map[service_id]

        for node_history in node_histories:
            node_history.node = specific_nodes[node_history.node_id]
        return node_histories

    def get_node_histories(
        self,
        workflow_history: AutomationWorkflowHistory,
        specific: bool = False,
    ) -> QuerySet[AutomationNodeHistory] | List[AutomationNodeHistory]:
        """Returns a queryset of AutomationNodeHistory by the workflow history."""

        node_histories = self._query_node_histories(
            AutomationNodeHistory.objects.filter(workflow_history=workflow_history)
        )
        if specific:
            return self._with_specific_nodes(node_histories)
        return node_histories

    def get_node_histories_for_workflow_histories(
        self,
        workflow_history_ids: Iterable[int],
        specific: bool = False,
    ) -> QuerySet[AutomationNodeHistory] | List[AutomationNodeHistory]:
        """Returns node histories for the given workflow history ids."""

        node_histories = self._query_node_histories(
            AutomationNodeHistory.objects.filter(
                workflow_history_id__in=workflow_history_ids
            )
        )
        if specific:
            return self._with_specific_nodes(node_histories)
        return node_histories

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

    def get_destination_labels(
        self, node_histories: List[AutomationNodeHistory]
    ) -> Dict[int, Dict[str, Any]]:
        """
        For each history entry whose node redirected execution to another node
        (e.g. the "Go to node" node), return a mapping that describes the node
        it jumped to, e.g.:
            {
                "id": <destination node id>,
                "type": <destination node type>,
                "label": <destination label>,
            }`

        The destination node belongs to the published workflow copy that
        actually ran, so its id cannot be resolved against the editor workflow.
        We therefore also return its type, allowing the frontend to display a
        human-readable name from the node type registry when the node has no
        custom label.
        """

        labels = {}
        for nh in node_histories:
            node = nh.node
            destination = node.get_type().get_history_destination_node(node)
            if destination is not None:
                labels[nh.id] = {
                    "id": destination.id,
                    "type": destination.get_type().type,
                    "label": destination.label,
                }
        return labels
