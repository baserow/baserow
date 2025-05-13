from typing import Dict, List, Optional

from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.models import Service
from baserow.core.services.utils import ServiceAdhocRefinements


class AutomationNodeDispatchContext(DispatchContext):
    def __init__(self, count: int, offset: int):
        self.cache = {}
        self.count = count
        self.offset = offset
        super().__init__()

    @property
    def is_publicly_searchable(self) -> bool:
        """
        Responsible for returning whether external service visitors
        can apply search or not.
        """

        return False

    @property
    def is_publicly_filterable(self) -> bool:
        """
        Responsible for returning whether external service visitors
        can apply filters or not.
        """

        return False

    @property
    def public_allowed_properties(self) -> Optional[Dict[str, Dict[int, List[str]]]]:
        """
        Return a Dict where keys are ["all", "external", "internal"] and values
        dicts. The internal dicts' keys are Service IDs and values are a list
        of Data Source field names.

        Returns None if public_allowed_properties shouldn't be included in the dispatch
        context. This is mainly to support a feature flag for this new feature.

        The field names are used to improve the security of the backend by
        ensuring only the minimum necessary data is exposed to the frontend.

        It is used to restrict the queryset as well as to discern which Data
        Source fields are external and safe (user facing) vs internal and
        sensitive (required only by the backend).
        """

        ...

    @property
    def is_publicly_sortable(self) -> bool:
        """
        Responsible for returning whether external service visitors
        can apply sortings or not.
        """

        return False

    def range(self, service: Service):
        """
        Should return the pagination requested for the given service.

        :params service: The service we want the pagination for.
        """

        return []

    def search_query(self) -> Optional[str]:
        """
        Responsible for returning the on-demand search query, depending
        on which module the `DispatchContext` is used by.
        """

        ...

    def searchable_fields(self) -> Optional[List[str]]:
        """
        Responsible for returning the on-demand searchable fields, depending
        on which module the `DispatchContext` is used by.
        """

        return []

    def filters(self) -> Optional[str]:
        """
        Responsible for returning the on-demand filters, depending
        on which module the `DispatchContext` is used by.
        """

        ...

    def sortings(self) -> Optional[str]:
        """
        Responsible for returning the on-demand sortings, depending
        on which module the `DispatchContext` is used by.
        """

        ...

    def validate_filter_search_sort_fields(
        self, fields: List[str], refinement: ServiceAdhocRefinements
    ):
        """
        Responsible for ensuring that all fields present in `fields`
        are allowed as a refinement for the given `refinement`. For example,
        if the `refinement` is `FILTER`, then all fields in `fields` need
        to be filterable.

        :param fields: The fields to validate.
        :param refinement: The refinement to validate.
        """

        ...
