from typing import Any, Dict, List, Optional, Union

from baserow.contrib.automation.data_providers.registries import (
    automation_data_provider_type_registry,
)
from baserow.contrib.automation.history.models import AutomationNodeResult
from baserow.contrib.automation.nodes.models import AutomationActionNode
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.models import Service
from baserow.core.services.utils import ServiceAdhocRefinements


class AutomationDispatchContext(DispatchContext):
    own_properties = ["workflow", "event_payload"]

    def __init__(
        self,
        workflow: AutomationWorkflow,
        event_payload: Optional[Union[Dict, List[Dict]]] = None,
        simulate_until_node: Optional[AutomationActionNode] = None,
        history_id: Optional[int] = None,
        current_iterations: Optional[Dict[int, int]] = None,
    ):
        """
        The `DispatchContext` implementation for automations. This context is provided
        to nodes, and can be modified so that following nodes are aware of a proceeding
        node's changes.

        :param workflow: The workflow that this dispatch context is associated with.
        :param event_payload: The event data from the trigger node, if any was
            provided, as this is optional.
        :param simulate_until_node: Stop simulating the dispatch once this node
            is reached.
        """

        self.workflow = workflow
        self.previous_nodes_results: Dict[int, Any] = {}
        self.simulate_until_node = simulate_until_node
        self.current_iterations: Dict[int, int] = {}

        if current_iterations:
            self.current_iterations = current_iterations

        if history_id:
            self._load_previous_results(history_id)

        services = (
            [self.simulate_until_node.service.specific]
            if self.simulate_until_node
            else None
        )

        force_outputs = (
            simulate_until_node.get_previous_service_outputs()
            if simulate_until_node
            else None
        )

        super().__init__(
            update_sample_data_for=services,
            use_sample_data=bool(self.simulate_until_node),
            force_outputs=force_outputs,
            event_payload=event_payload,
        )

    def clone(self, **kwargs):
        new_context = super().clone(**kwargs)
        new_context.previous_nodes_results = {**self.previous_nodes_results}
        new_context.current_iterations = {**self.current_iterations}
        return new_context

    def _load_previous_results(self, history_id: int):
        """
        Updates the previous_nodes_results using data from the node
        history related to the history_id.
        """

        previous_results = AutomationNodeResult.objects.filter(
            node_history__workflow_history_id=history_id
        ).select_related("node_history__node")
        for result in previous_results:
            self.previous_nodes_results[result.node_history.node_id] = result.result

    @property
    def data_provider_registry(self):
        return automation_data_provider_type_registry

    def get_timezone_name(self) -> str:
        """
        TODO: Get the timezone from the application settings. For now, returns
            the default of "UTC". See: https://github.com/baserow/baserow/issues/4157
        """

        return super().get_timezone_name()

    def range(self, service: Service):
        return [0, None]

    def sortings(self) -> Optional[str]:
        return None

    def filters(self) -> Optional[str]:
        return None

    def is_publicly_sortable(self) -> bool:
        return False

    def is_publicly_filterable(self) -> bool:
        return False

    def is_publicly_searchable(self) -> bool:
        return False

    def public_allowed_properties(self) -> Optional[Dict[str, Dict[int, List[str]]]]:
        return {}

    def search_query(self) -> Optional[str]:
        return None

    def searchable_fields(self):
        return []

    def validate_filter_search_sort_fields(
        self, fields: List[str], refinement: ServiceAdhocRefinements
    ): ...
