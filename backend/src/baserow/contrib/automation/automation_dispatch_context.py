from typing import Any, Dict, List, Optional, Union

from baserow.contrib.automation.data_providers.registries import (
    automation_data_provider_type_registry,
)
from baserow.contrib.automation.history.handler import AutomationHistoryHandler
from baserow.contrib.automation.history.models import (
    AutomationNodeHistory,
)
from baserow.contrib.automation.nodes.models import AutomationActionNode
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.cache import local_cache
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.models import Service
from baserow.core.services.utils import ServiceAdhocRefinements


class AutomationDispatchContext(DispatchContext):
    own_properties = ["workflow", "event_payload", "history"]

    def __init__(
        self,
        workflow: AutomationWorkflow,
        history: AutomationNodeHistory,
        event_payload: Optional[Union[Dict, List[Dict]]] = None,
        simulate_until_node: Optional[AutomationActionNode] = None,
        current_iterations: Optional[Dict[int, int]] = None,
    ):
        """
        The `DispatchContext` implementation for automations. This context is provided
        to nodes, and can be modified so that following nodes are aware of a proceeding
        node's changes.

        :param workflow: The workflow that this dispatch context is associated with.
        :param history: The AutomationWorkflowHistory from which the
            workflow's event payload and node results are derived.
        :param event_payload: The event data from the trigger node, if any was
            provided, as this is optional.
        :param simulate_until_node: Stop simulating the dispatch once this node
            is reached.
        :param current_iterations: Used by the Iterator node's children.
        """

        self.workflow = workflow
        self.history = history
        self.simulate_until_node = simulate_until_node
        self.current_iterations: Dict[int, int] = {}

        if current_iterations:
            # The keys are strings due to JSON serialization by Celery. We need
            # to convert them back to ints.
            self.current_iterations = {int(k): v for k, v in current_iterations.items()}

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
        new_context.current_iterations = {**self.current_iterations}
        return new_context

    def get_iteration_path(self, node):
        """
        Compute the current iteration path for the given node.
        """
        parent_nodes = node.get_parent_nodes()

        return ".".join([str(self.current_iterations[p.id]) for p in parent_nodes])

    def _get_previous_result_cache_key(self, node) -> Optional[str]:
        return f"wa_previous_node_result_{self.history.id}_{node.id}"

    @property
    def data_provider_registry(self):
        return automation_data_provider_type_registry

    def get_previous_node_result(self, node) -> Dict[int, Any]:
        # We don't need to cache per iteration path because it won't change in this
        # dispatch
        return local_cache.get(
            self._get_previous_result_cache_key(node),
            lambda: AutomationHistoryHandler().get_node_result(
                self.history, node, self.get_iteration_path(node)
            ),
        )

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

    @property
    def is_publicly_sortable(self) -> bool:
        return False

    @property
    def is_publicly_filterable(self) -> bool:
        return False

    @property
    def is_publicly_searchable(self) -> bool:
        return False

    @property
    def public_allowed_properties(self) -> Optional[Dict[str, Dict[int, List[str]]]]:
        return None

    def search_query(self) -> Optional[str]:
        return None

    def searchable_fields(self):
        return []

    def validate_filter_search_sort_fields(
        self, fields: List[str], refinement: ServiceAdhocRefinements
    ): ...
