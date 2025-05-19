from typing import Dict, List, Optional, Union

from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.models import Service
from baserow.core.services.utils import ServiceAdhocRefinements


class AutomationDispatchContext(DispatchContext):
    own_properties = ["event_payload", "automation"]

    def __init__(
        self,
        workflow: AutomationWorkflow,
        event_payload: Optional[Union[Dict, List[Dict]]],
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
        self.event_payload = event_payload
        super().__init__()

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
