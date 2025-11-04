from typing import Any, Dict, List, Optional, Union

from baserow.contrib.automation.data_providers.registries import (
    automation_data_provider_type_registry,
)
from baserow.contrib.automation.nodes.models import AutomationActionNode, AutomationNode
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.models import Service
from baserow.core.services.types import DispatchResult
from baserow.core.services.utils import ServiceAdhocRefinements


class AutomationDispatchContext(DispatchContext):
    own_properties = ["workflow", "event_payload", "simulate_until_node"]

    def __init__(
        self,
        workflow: AutomationWorkflow,
        event_payload: Optional[Union[Dict, List[Dict]]] = None,
        simulate_until_node: Optional[AutomationActionNode] = None,
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
        self.dispatch_history: List[int] = []
        self.simulate_until_node = simulate_until_node
        self.current_iterations: Dict[int, int] = {}

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
        new_context.dispatch_history = list(self.dispatch_history)

        return new_context

    @property
    def data_provider_registry(self):
        return automation_data_provider_type_registry

    def get_timezone_name(self) -> str:
        """
        TODO: Get the timezone from the application settings. For now, returns
            the default of "UTC". See: https://github.com/baserow/baserow/issues/4157
        """

        return super().get_timezone_name()

    def _register_node_result(
        self, node: AutomationNode, dispatch_data: Dict[str, Any]
    ):
        self.previous_nodes_results[node.id] = dispatch_data

    def after_dispatch(self, node: AutomationNode, dispatch_result: DispatchResult):
        """
        This method is called after each node dispatch. It can be used
        to perform any final actions or cleanup.
        """

        self.dispatch_history.append(node.id)
        self._register_node_result(node, dispatch_result.data)

    def set_current_iteration(self, node, index):
        self.current_iterations[node.id] = index

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
    ):
        ...
