from typing import Any, Dict, List, Optional, Union

from baserow.contrib.automation.data_providers.registries import (
    automation_data_provider_type_registry,
)
from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.models import Service
from baserow.core.services.types import DispatchResult
from baserow.core.services.utils import ServiceAdhocRefinements


class AutomationDispatchContext(DispatchContext):
    own_properties = ["workflow"]

    def __init__(
        self,
        workflow: AutomationWorkflow,
        event_payload: Optional[Union[Dict, List[Dict]]] = None,
    ):
        """
        The `DispatchContext` implementation for automations. This context is provided
        to nodes, and can be modified so that following nodes are aware of a proceeding
        node's changes.

        :param event_payload: The event data from the trigger node, if any was
            provided, as this is optional.
        :param workflow: The workflow that this dispatch context is associated with.
        """

        self.workflow = workflow
        self.previous_nodes_results: Dict[int, Any] = {}
        self.dispatch_history: List[int] = []
        self._initialize_trigger_results(event_payload)
        super().__init__()

    def clone(self, **kwargs):
        new_context = super().clone(**kwargs)
        new_context.previous_nodes_results = {**self.previous_nodes_results}
        new_context.dispatch_history = list(self.dispatch_history)

        return new_context

    @property
    def data_provider_registry(self):
        return automation_data_provider_type_registry

    def _initialize_trigger_results(
        self,
        event_payload: Optional[Union[List[Dict[Any, Any]], Dict[Any, Any]]] = None,
    ):
        """
        Responsible for finding the trigger node in the workflow and storing the
        event payload in the `previous_nodes_results` dictionary, if we've been
        given any.

        :param event_payload: The event data from the trigger node.
        """

        trigger_node = self.workflow.get_trigger(specific=False)
        if event_payload and trigger_node:
            self._register_node_result(trigger_node, event_payload)

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

    def range(self, service: Service):
        pass

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
