from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from baserow.core.formula.runtime_formula_context import RuntimeFormulaContext
from baserow.core.services.models import Service
from baserow.core.services.types import RuntimeFormulaContextSubClass
from baserow.core.services.utils import ServiceAdhocRefinements


class DispatchContext(RuntimeFormulaContext, ABC):
    own_properties = []

    def __init__(self):
        self.cache = {}  # can be used by data providers to save queries
        super().__init__()

    @abstractmethod
    def range(self, service: Service):
        """
        Should return the pagination requested for the given service.

        :params service: The service we want the pagination for.
        """

    @classmethod
    def from_context(
        cls, context: RuntimeFormulaContextSubClass, **kwargs
    ) -> RuntimeFormulaContextSubClass:
        """
        Return a new DispatchContext instance from the given context, without
        losing the original cached data.

        :params context: The context to create a new DispatchContext instance from.
        """

        new_values = {}
        for prop in cls.own_properties:
            new_values[prop] = getattr(context, prop)
        new_values.update(kwargs)

        new_context = cls(**new_values)
        new_context.cache = {**context.cache}

        return new_context

    @property
    @abstractmethod
    def is_publicly_searchable(self) -> bool:
        """
        Responsible for returning whether external users can apply search or not.
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
        Responsible for returning whether external users can apply filters or not.
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
        Responsible for returning whether external users can apply sortings or not.
        """

    @abstractmethod
    def sortings(self) -> Optional[str]:
        """
        Responsible for returning the on-demand sortings, depending
        on which module the `DispatchContext` is used by.
        """

    @property
    @abstractmethod
    def public_formula_fields(self) -> Optional[Dict[str, Dict[int, List[str]]]]:
        """
        Return a Dict where keys are ["all", "external", "internal"] and values
        dicts. The internal dicts' keys are Service IDs and values are a list
        of Data Source field names.

        Returns None if public_formula_fields shouldn't be included in the dispatch
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
