from functools import cached_property
from typing import TYPE_CHECKING, Dict, List, Optional, Type

from django.contrib.auth import get_user_model
from django.http import HttpRequest

from baserow.contrib.builder.data_providers.registries import (
    builder_data_provider_type_registry,
)
from baserow.contrib.builder.data_sources.exceptions import (
    DataSourceRefinementForbidden,
)
from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.handler import BuilderHandler
from baserow.contrib.builder.pages.models import Page
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.utils import ServiceAdhocRefinements

if TYPE_CHECKING:
    from baserow.contrib.builder.elements.models import Element
    from baserow.contrib.builder.elements.registries import ElementType
    from baserow.core.workflow_actions.models import WorkflowAction

CACHE_KEY_PREFIX = "used_properties_for_page"

User = get_user_model()

SENTINEL = "__no_results__"


class BuilderDispatchContext(DispatchContext):
    own_properties = [
        "request",
        "page",
        "workflow_action",
        "data_source",
        "offset",
        "count",
        "only_record_id",
        "only_expose_public_allowed_properties",
    ]

    def __init__(
        self,
        request: HttpRequest,
        page: Page,
        workflow_action: Optional["WorkflowAction"] = None,
        data_source: Optional["DataSource"] = None,
        offset: Optional[int] = None,
        count: Optional[int] = None,
        only_expose_public_allowed_properties: Optional[bool] = True,
        **kwargs,
    ):
        """
        Dispatch context used in the builder.

        :param request: The HTTP request from the view.
        :param page: The page related to the dispatch.
        :param workflow_action: The workflow action being executed, if any.
        :param data_source: The data source initially being executed, if any.
        :param offset: When we dispatch a list service, starts by that offset.
        :param count: When we dispatch a list service returns that max amount of record.
        :param record_id: If we want to narrow down the results of a list service to
          only the record with this Id.
        :param only_expose_public_allowed_properties: Determines whether only public
            allowed properties should be exposed. Defaults to True.
        """

        self.request = request
        self.page = page
        self.workflow_action = workflow_action
        self.data_source = data_source

        # Overrides the `request` GET offset/count values.
        self.offset = offset
        self.count = count
        self.only_expose_public_allowed_properties = (
            only_expose_public_allowed_properties
        )

        super().__init__(**kwargs)

        # Early call to quickly trigger a validation error
        self.request_data

    @cached_property
    def element(self) -> "Element":
        """
        The element associated with the request if any.
        """

        return self.request_data.get("data_source", {}).get("element")

    @cached_property
    def request_data(self) -> Dict:
        """
        Returns the request data potentially deserialized if the query was a multipart.
        """

        from baserow.contrib.builder.api.data_sources.serializers import (
            DynamicMetadataSerializer,
        )

        serializer = DynamicMetadataSerializer(
            data=getattr(self.request, "data", {}).get("metadata", {}),
            context={"page": self.page},
        )
        serializer.is_valid(raise_exception=True)

        return serializer.validated_data

    @property
    def data_provider_registry(self):
        return builder_data_provider_type_registry

    @property
    def element_type(self) -> Optional[Type["ElementType"]]:
        """
        If we have been provided with an `element` in the constructor, we will
        return its element type.
        :return: An `ElementType` subclass.
        """

        if not self.element:
            return None

        return self.element.get_type()  # type: ignore

    def get_timezone_name(self) -> str:
        """
        Returns the timezone from the user data provider.
        """

        return self.request_data.get("user", {}).get(
            "timezone", super().get_timezone_name()
        )

    def range(self, service):
        """
        Return page range from the `offset`, `count` kwargs,
        or the GET parameters.
        """

        if self.offset is not None and self.count is not None:
            offset = self.offset
            count = self.count
        else:
            try:
                offset = int(self.request.GET.get("offset", 0))
            except ValueError:
                offset = 0

            count = None
            if "count" in self.request.GET:
                try:
                    count = int(self.request.GET["count"])
                except ValueError:
                    pass

        # max prevent negative values
        return [
            max(0, offset),
            max(0, count) if count is not None else None,
        ]

    def get_element_property_options(self) -> Dict[str, Dict[str, bool]]:
        """
        Responsible for returning the property options for the element.
        The property options are cached if they haven't already been, so
        that they can be re-used by other methods.

        :raises DataSourceRefinementForbidden: If `self.element` is `None`.
        """

        # We need an element to be able to validate filter, search and sort fields.
        if not self.element:
            raise DataSourceRefinementForbidden(
                "An element is required to validate filter, search and sort fields."
            )

        # And more specifically, it needs to be a collection element.
        if not getattr(self.element_type, "is_collection_element", False):
            raise DataSourceRefinementForbidden(
                "A collection element is required to validate filter, "
                "search and sort fields."
            )

        if "element_property_options" not in self.cache:
            property_options = ElementHandler().get_element_property_options(
                self.element
            )
            self.cache["element_property_options"] = property_options

        return self.cache["element_property_options"]

    @property
    def is_publicly_searchable(self) -> bool:
        """
        Responsible for returning whether this `element` is searchable or not.
        This is determined by the `is_publicly_searchable` property option on the
        collection element type.
        :return: A boolean.
        """

        return getattr(self.element_type, "is_publicly_searchable", False)

    def search_query(self) -> Optional[str]:
        """
        In a `BuilderDispatchContext`, we will use the HTTP request
        to return the `search_query` provided by the frontend.

        :return: A search query string.
        """

        return self.request.GET.get("search_query", None)

    def searchable_fields(self) -> Optional[List[str]]:
        """
        In a `BuilderDispatchContext`, we will use the `element` to
        determine which fields are searchable, by checking the `property_options`.

        :raises: DataSourceRefinementForbidden: If `self.element` is `None`.
        :return: A list of searchable fields.
        """

        property_options = self.get_element_property_options()
        return [
            schema_property
            for schema_property, options in property_options.items()
            if options["searchable"]
        ]

    @property
    def is_publicly_filterable(self) -> bool:
        """
        Responsible for returning whether this `element` is filterable or not.
        This is determined by the `is_publicly_filterable` property option on the
        collection element type.
        :return: A boolean.
        """

        return getattr(self.element_type, "is_publicly_filterable", False)

    def filters(self) -> Optional[str]:
        """
        In a `BuilderDispatchContext`, we will use the HTTP request's
        serialized `filters`, pass it to the `AdHocFilters` class, and
        return the result.

        :return: A JSON serialized string.
        """

        return self.request.GET.get("filters", None)

    @property
    def is_publicly_sortable(self) -> bool:
        """
        Responsible for returning whether this `element` is sortable or not.
        This is determined by the `is_publicly_sortable` property option on the
        collection element type.
        :return: A boolean.
        """

        return getattr(self.element_type, "is_publicly_sortable", False)

    def sortings(self) -> Optional[str]:
        """
        In a `BuilderDispatchContext`, we will use the HTTP request
        to return the `order_by` provided by the frontend.

        :return: A sort string.
        """

        return self.request.GET.get("order_by", None)

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
        :raises DataSourceRefinementForbidden: If a field is not allowed for the given
            refinement.
        """

        # Get the property options for the element.
        property_options = self.get_element_property_options()

        # The filterable/sortable/searchable options for the given fields.
        # If a `field` has been provided that doesn't exist in the property options
        # table, it means it hasn't been configured by the page designer, so all
        # three refinement options are disabled.
        field_property_options = {
            schema_property: property_options.get(
                schema_property,
                {"filterable": False, "sortable": False, "searchable": False},
            )
            for schema_property in fields
        }

        for field_property, field_options in field_property_options.items():
            # If the property is not allowed for the given refinement, raise an error.
            model_field = ServiceAdhocRefinements.to_model_field(refinement)
            if not field_options[model_field]:
                raise DataSourceRefinementForbidden(
                    f"{field_property} is not a {model_field} field."
                )

    @property
    def public_allowed_properties(self) -> Optional[Dict[str, Dict[int, List[str]]]]:
        """
        Return a Dict where keys are ["all", "external", "internal"] and values
        dicts. The internal dicts' keys are Service IDs and values are a list
        of Data Source field names.

        Returns None if field names shouldn't be included in the dispatch
        context. This is mainly to support a feature flag for this new feature.

        The field names are used to improve the security of the backend by
        ensuring only the minimum necessary data is exposed to the frontend.

        It is used to restrict the queryset as well as to discern which Data
        Source fields are external and safe (user facing) vs internal and
        sensitive (required only by the backend).
        """

        if not self.only_expose_public_allowed_properties:
            return None

        return BuilderHandler().get_builder_public_properties(
            self.request.user_source_user,
            self.page.builder,
        )
