from abc import ABC
from typing import Any, Dict, List, Optional

from django.contrib.auth.models import AbstractUser

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
        actor: Optional[AbstractUser] = None,
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
        :param actor: The user this dispatch acts as, for services that have no
            integration to supply one.
        """

        self.cache = {}  # can be used by data providers to save queries
        self.only_record_id = only_record_id
        self.update_sample_data_for = update_sample_data_for
        self.use_sample_data = use_sample_data
        self.force_outputs = force_outputs
        self.event_payload = event_payload
        self.actor = actor
        super().__init__()

    def range(self, service: Service) -> tuple[int, int | None]:
        """
        Should return the pagination requested for the given service. Defaults to
        the first page at the service's own default size, which suits every
        context that has no pagination surface of its own.

        :params service: The service we want the pagination for.
        :return: a tuple were the first value is the offset to apply and the second
          value is the count of records to return. The count can be None it which case
          the default number of record should be returned.
        """

        return 0, None

    def clone(self, **kwargs) -> RuntimeFormulaContextSubClass:
        """
        Return a new DispatchContext instance cloned from the current context, without
        losing the original cached data and call stack but updating some properties.

        The actor is carried over explicitly rather than via `own_properties`, so
        it survives subclasses that replace that list.
        """

        new_values = {}
        for prop in self.own_properties:
            new_values[prop] = getattr(self, prop)
        new_values.update(kwargs)

        actor = new_values.pop("actor", self.actor)
        new_context = self.__class__(**new_values)
        new_context.actor = actor
        new_context.cache = {**self.cache}
        new_context.call_stack = set(self.call_stack)

        return new_context

    def is_adhoc_refinable(self, service: Service) -> bool:
        """
        Responsible for returning whether the request's adhoc refinements
        (search, filters and sortings) may be applied when dispatching the
        given service. By default they apply to every dispatched service,
        but subclasses can restrict them to the service the request actually
        targets, so that refinements don't leak into nested dispatches (e.g.
        a data source referenced by another data source's filter formula).

        :param service: The service that is currently being dispatched.
        :return: Whether adhoc refinements may be applied to this service.
        """

        return True

    @property
    def is_publicly_searchable(self) -> bool:
        """
        Responsible for returning whether external service visitors
        can apply search or not. Defaults to False, only contexts with a public
        surface can opt in.
        """

        return False

    def search_query(self) -> Optional[str]:
        """
        Responsible for returning the on-demand search query, depending
        on which module the `DispatchContext` is used by.
        """

        return None

    def searchable_fields(self) -> List[str]:
        """
        Responsible for returning the on-demand searchable fields, depending
        on which module the `DispatchContext` is used by.
        """

        return []

    @property
    def is_publicly_filterable(self) -> bool:
        """
        Responsible for returning whether external service visitors
        can apply filters or not. Defaults to False, only contexts with a public
        surface can opt in.
        """

        return False

    def filters(self) -> Optional[str]:
        """
        Responsible for returning the on-demand filters, depending
        on which module the `DispatchContext` is used by.
        """

        return None

    @property
    def is_publicly_sortable(self) -> bool:
        """
        Responsible for returning whether external service visitors
        can apply sortings or not. Defaults to False, only contexts with a public
        surface can opt in.
        """

        return False

    def sortings(self) -> Optional[str]:
        """
        Responsible for returning the on-demand sortings, depending
        on which module the `DispatchContext` is used by.
        """

        return None

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

        return None

    def validate_filter_search_sort_fields(
        self, fields: List[str], refinement: ServiceAdhocRefinements
    ):
        """
        Responsible for ensuring that all fields present in `fields`
        are allowed as a refinement for the given `refinement`. For example,
        if the `refinement` is `FILTER`, then all fields in `fields` need
        to be filterable.

        Only reachable when the context declares itself publicly filterable,
        sortable or searchable, so the default raises: a context that opts into
        ad hoc refinements has to say which fields are allowed rather than
        silently accepting every field.

        :param fields: The fields to validate.
        :param refinement: The refinement to validate.
        """

        raise NotImplementedError(
            f"{self.__class__.__name__} allows ad hoc refinements but doesn't "
            "validate the fields they point at."
        )
