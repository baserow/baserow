from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from baserow.core.formula.runtime_formula_context import RuntimeFormulaContext
from baserow.core.services.models import Service
from baserow.core.services.types import RuntimeFormulaContextSubClass
from baserow.core.services.utils import ServiceAdhocRefinements


class DispatchContext(RuntimeFormulaContext, ABC):
    own_properties = [
        "only_record_id",
        "update_sample_data_for",
        "use_sample_data",
        "force_outputs",
        "event_payload",
    ]

    """
    Should return the record id requested for the given service. Used by list
    services to select only one record. For instance by the builder current record
    data provider to narrow down the result of a list service.
    """
    only_record_id = None

    def __init__(
        self,
        only_record_id=None,
        event_payload: Any = None,
        update_sample_data_for: Optional[List[Service]] = None,
        use_sample_data: bool = False,
        force_outputs: Dict[int, str] = None,
    ):
        """
        This abstract base class provides context needed by specific
        services when they are dispatched during service execution.

        :param only_record_id: Filters a queryset by a specific ID.
        :param event_payload: The event data for an optional trigger if any.
        :param update_sample_data_for: Updates the sample_data for only the
            provided services. Used in conjunction with use_sample_data.
        :param use_sample_data: Whether to use or update the sample_data.
        :param force_outputs: Mapping of service IDs and previous service
            outputs. Can be used to force a specific service to be dispatched.
        """

        self.cache = {}  # can be used by data providers to save queries
        self.only_record_id = only_record_id
        self.update_sample_data_for = update_sample_data_for
        self.use_sample_data = use_sample_data
        self.force_outputs = force_outputs
        self.event_payload = event_payload
        super().__init__()

    @abstractmethod
    def range(self, service: Service) -> tuple[int, int | None]:
        """
        Should return the pagination requested for the given service.

        :params service: The service we want the pagination for.
        :return: a tuple were the first value is the offset to apply and the second
          value is the count of records to return. The count can be None it which case
          the default number of record should be returned.
        """

    def clone(self, **kwargs) -> RuntimeFormulaContextSubClass:
        """
        Return a new DispatchContext instance cloned from the current context, without
        losing the original cached data and call stack but updating some properties.
        """

        new_values = {}
        for prop in self.own_properties:
            new_values[prop] = getattr(self, prop)
        new_values.update(kwargs)

        new_context = self.__class__(**new_values)
        new_context.cache = {**self.cache}
        new_context.call_stack = set(self.call_stack)

        return new_context

    @property
    @abstractmethod
    def is_publicly_searchable(self) -> bool:
        """
        Responsible for returning whether external service visitors
        can apply search or not.
        """

    @abstractmethod
    def search_query(self) -> Optional[str]:
        """
        Responsible for returning the on-demand search query, depending
        on which module the `DispatchContext` is used by.
        """

    @abstractmethod
    def searchable_fields(self) -> Optional[List[str]]:
        """
        Responsible for returning the on-demand searchable fields, depending
        on which module the `DispatchContext` is used by.
        """

        return []

    @property
    @abstractmethod
    def is_publicly_filterable(self) -> bool:
        """
        Responsible for returning whether external service visitors
        can apply filters or not.
        """

    @abstractmethod
    def filters(self) -> Optional[str]:
        """
        Responsible for returning the on-demand filters, depending
        on which module the `DispatchContext` is used by.
        """

    @property
    @abstractmethod
    def is_publicly_sortable(self) -> bool:
        """
        Responsible for returning whether external service visitors
        can apply sortings or not.
        """

    @abstractmethod
    def sortings(self) -> Optional[str]:
        """
        Responsible for returning the on-demand sortings, depending
        on which module the `DispatchContext` is used by.
        """

    @property
    @abstractmethod
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

    @abstractmethod
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
