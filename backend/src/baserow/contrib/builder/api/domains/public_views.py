from typing import Any, Dict, List

from django.contrib.auth.models import AbstractUser, AnonymousUser
from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.applications.serializers import (
    PublicPolymorphicApplicationResponseSerializer,
)
from baserow.api.decorators import map_exceptions
from baserow.api.errors import ERROR_PERMISSION_DENIED
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.services.errors import (
    ERROR_SERVICE_FILTER_PROPERTY_DOES_NOT_EXIST,
    ERROR_SERVICE_IMPROPERLY_CONFIGURED,
    ERROR_SERVICE_INVALID_DISPATCH_CONTEXT,
    ERROR_SERVICE_INVALID_DISPATCH_CONTEXT_CONTENT,
    ERROR_SERVICE_SORT_PROPERTY_DOES_NOT_EXIST,
    ERROR_SERVICE_UNEXPECTED_DISPATCH_ERROR,
)
from baserow.api.utils import (
    DiscriminatorCustomFieldsMappingSerializer,
    apply_exception_mapping,
)
from baserow.contrib.builder.api.data_sources.errors import (
    ERROR_DATA_DOES_NOT_EXIST,
    ERROR_DATA_SOURCE_DOES_NOT_EXIST,
    ERROR_DATA_SOURCE_REFINEMENT_FORBIDDEN,
)
from baserow.contrib.builder.api.data_sources.serializers import (
    DispatchDataSourceRequestSerializer,
)
from baserow.contrib.builder.api.domains.serializers import (
    PublicDataSourceSerializer,
    PublicElementSerializer,
)
from baserow.contrib.builder.api.elements.errors import ERROR_ELEMENT_DOES_NOT_EXIST
from baserow.contrib.builder.api.pages.errors import ERROR_PAGE_DOES_NOT_EXIST
from baserow.contrib.builder.api.workflow_actions.serializers import (
    BuilderWorkflowActionSerializer,
)
from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.exceptions import (
    DataSourceDoesNotExist,
    DataSourceRefinementForbidden,
)
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.domains.service import DomainService
from baserow.contrib.builder.elements.exceptions import ElementDoesNotExist
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.errors import ERROR_BUILDER_DOES_NOT_EXIST
from baserow.contrib.builder.exceptions import BuilderDoesNotExist
from baserow.contrib.builder.handler import BuilderHandler
from baserow.contrib.builder.pages.exceptions import PageDoesNotExist
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.service import BuilderService
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.builder.workflow_actions.service import (
    BuilderWorkflowActionService,
)
from baserow.core.cache import global_cache
from baserow.core.exceptions import ApplicationDoesNotExist, PermissionException
from baserow.core.services.exceptions import (
    DoesNotExist,
    InvalidContextContentDispatchException,
    InvalidContextDispatchException,
    ServiceFilterPropertyDoesNotExist,
    ServiceImproperlyConfiguredDispatchException,
    ServiceSortPropertyDoesNotExist,
    UnexpectedDispatchException,
)
from baserow.core.services.registries import service_type_registry
from baserow.core.user_sources.user_source_user import UserSourceUser

# The duration of the cached public element, data source and workflow action API views.
BUILDER_PUBLIC_RECORDS_CACHE_TTL_SECONDS = 60 * 60

# The duration of the cached public `get_public_builder_by_domain_name` view.
BUILDER_PUBLIC_BUILDER_BY_DOMAIN_TTL_SECONDS = 60 * 60


class ForcedPublicPolymorphicApplicationResponseSerializer(
    PublicPolymorphicApplicationResponseSerializer
):
    forced_type = "builder"


class PublicBuilderByDomainNameView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="domain_name",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="Returns the builder published for the given domain name.",
            )
        ],
        tags=["Builder public"],
        operation_id="get_public_builder_by_domain_name",
        description=(
            "Returns the public serialized version of the builder for "
            "the given domain name and its pages ."
        ),
        responses={
            200: ForcedPublicPolymorphicApplicationResponseSerializer,
            404: get_error_schema(["ERROR_BUILDER_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({BuilderDoesNotExist: ERROR_BUILDER_DOES_NOT_EXIST})
    def get(self, request: Request, domain_name: str):
        """
        Responds with a serialized version of the builder related to the query.
        Try to match a published builder for the given domain name. Used to display
        the public site.
        """

        data = global_cache.get(
            DomainHandler.get_public_builder_by_domain_cache_key(domain_name),
            default=lambda: self._get_public_builder_by_domain(domain_name),
            timeout=BUILDER_PUBLIC_BUILDER_BY_DOMAIN_TTL_SECONDS,
        )
        return Response(data)

    def _get_public_builder_by_domain(self, domain_name: str):
        """
        Returns a serialized builder which has a domain matching `domain_name`.

        Only requested if the public get-by-domain cache is stale, or if the
        application has been re-published.

        :param domain_name: the domain name to match.
        :return: a publicly serialized builder.
        """

        # Should be accessed by anonymous user
        builder = DomainService().get_public_builder_by_domain_name(
            AnonymousUser(), domain_name
        )
        return PublicPolymorphicApplicationResponseSerializer(builder).data


class PublicBuilderByIdView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="builder_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the builder related to the "
                "provided Id and its pages.",
            )
        ],
        tags=["Builder public"],
        operation_id="get_public_builder_by_id",
        description=(
            "Returns the public serialized version of the builder and its pages for "
            "the given builder id."
        ),
        responses={
            200: ForcedPublicPolymorphicApplicationResponseSerializer,
            404: get_error_schema(["ERROR_BUILDER_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            BuilderDoesNotExist: ERROR_BUILDER_DOES_NOT_EXIST,
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
        }
    )
    def get(self, request, builder_id):
        """
        Returns a public version of the builder for the given id. This version can be
        used to display the preview before publishing.
        """

        builder = BuilderService().get_builder(request.user, builder_id)
        return Response(PublicPolymorphicApplicationResponseSerializer(builder).data)


class PublicElementsView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="page_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the elements of the page related to the "
                "provided Id.",
            )
        ],
        tags=["Builder elements"],
        operation_id="list_public_builder_page_elements",
        description=(
            "Lists all the elements of the page related to the provided parameter. "
            "If the user is Anonymous, the page must belong to a published builder "
            "instance to being accessible."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                element_type_registry, PublicElementSerializer, many=True
            ),
            404: get_error_schema(["ERROR_PAGE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, page_id: int):
        """
        Responds with a list of serialized elements that belongs to the given page id.
        """

        if PageHandler().is_published_page(page_id):
            data = global_cache.get(
                PageHandler.get_page_public_records_cache_key(
                    page_id, request.user_source_user, "elements"
                ),
                default=lambda: self._get_public_page_elements(
                    request.user_source_user, page_id
                ),
                timeout=BUILDER_PUBLIC_RECORDS_CACHE_TTL_SECONDS,
            )
        else:
            data = self._get_public_page_elements(request.user, page_id)

        return Response(data)

    def _get_public_page_elements(
        self, user: AbstractUser, page_id: int
    ) -> List[Dict[str, Any]]:
        """
        Returns a list of serialized elements that belong to the given page id.

        Only requested if the public elements cache is stale, or if the page is
        being previewed.

        :param user: the user requesting the elements.
        :param page_id: the page id.
        :return: a list of serialized elements.
        """

        page = PageHandler().get_page(page_id)
        elements = ElementService().get_elements(user, page)
        workspace = page.builder.get_workspace()

        return [
            element_type_registry.get_serializer(element, PublicElementSerializer).data
            for element in elements
            if not element.get_type().is_deactivated(workspace)
        ]


class PublicDataSourcesView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="page_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the data_sources of the page related to the "
                "provided Id if the related builder is public.",
            )
        ],
        tags=["Builder data sources"],
        operation_id="list_public_builder_page_data_sources",
        description=(
            "Lists all the data_sources of the page related to the provided parameter "
            "if the builder is public."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                service_type_registry, PublicDataSourceSerializer, many=True
            ),
            404: get_error_schema(["ERROR_PAGE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, page_id: int):
        """
        Responds with a list of serialized data_sources that belong to the page if the
        user has access to it.
        """

        if PageHandler().is_published_page(page_id):
            data = global_cache.get(
                PageHandler.get_page_public_records_cache_key(
                    page_id, request.user_source_user, "data_sources"
                ),
                default=lambda: self._get_public_page_data_sources(
                    request.user_source_user, request.user_source_user, page_id
                ),
                timeout=BUILDER_PUBLIC_RECORDS_CACHE_TTL_SECONDS,
            )
        else:
            data = self._get_public_page_data_sources(
                request.user, request.user_source_user, page_id
            )

        return Response(data)

    def _get_public_page_data_sources(
        self, user: AbstractUser, user_source_user: UserSourceUser, page_id: int
    ):
        """
        Returns a list of serialized data sources that belong to the given page id.

        Only requested if the public data sources cache is stale, or if the page is
        being previewed.

        :param user: the user requesting the data sources.
        :param user_source_user: the user source user we want the data for.
        :param page_id: the page id.
        :return: a list of serialized data sources.
        """

        page = PageHandler().get_page(page_id)
        data_sources = DataSourceService().get_data_sources(user, page)

        public_properties = BuilderHandler().get_builder_public_properties(
            user_source_user, page.builder
        )
        allowed_fields = []
        for fields in public_properties["external"].values():
            allowed_fields.extend(fields)

        return [
            service_type_registry.get_serializer(
                data_source.service,
                PublicDataSourceSerializer,
                context={"data_source": data_source, "allowed_fields": allowed_fields},
            ).data
            for data_source in data_sources
            if data_source.service and data_source.service.integration_id
        ]


class PublicBuilderWorkflowActionsView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="page_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the public workflow actions of the page related "
                "to the provided Id.",
            )
        ],
        tags=["Builder workflow actions"],
        operation_id="list_public_builder_page_workflow_actions",
        description=(
            "Lists all the workflow actions with their public accessible data. Some "
            "configuration might be omitted for security reasons such as passwords or "
            "PII."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                builder_workflow_action_type_registry,
                BuilderWorkflowActionSerializer,
                many=True,
                name_prefix="public_",
                extra_params={"public": True},
            ),
            404: get_error_schema(["ERROR_PAGE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
        }
    )
    def get(self, request: Request, page_id: int):
        """ "
        Responds with a list of serialized workflow actions that belongs to the given
        page id.
        """

        if PageHandler().is_published_page(page_id):
            data = global_cache.get(
                PageHandler.get_page_public_records_cache_key(
                    page_id, request.user_source_user, "workflow_actions"
                ),
                default=lambda: self._get_public_page_workflow_actions(
                    request.user_source_user, page_id
                ),
                timeout=BUILDER_PUBLIC_RECORDS_CACHE_TTL_SECONDS,
            )
        else:
            data = self._get_public_page_workflow_actions(request.user, page_id)

        return Response(data)

    def _get_public_page_workflow_actions(self, user: AbstractUser, page_id: int):
        """
        Returns a list of serialized workflow actions that belong to the given page id.

        Only requested if the public workflow actions cache is stale, or if the page is
        being previewed.

        :param user: the user requesting the actions.
        :param page_id: the page id.
        :return: a list of serialized workflow actions.
        """

        page = PageHandler().get_page(page_id)
        workflow_actions = BuilderWorkflowActionService().get_workflow_actions(
            user, page
        )

        return [
            builder_workflow_action_type_registry.get_serializer(
                workflow_action,
                BuilderWorkflowActionSerializer,
                extra_params={"public": True},
            ).data
            for workflow_action in workflow_actions
        ]


class PublicDispatchDataSourceView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="data_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the data_source you want to call the dispatch "
                "for",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder data sources"],
        operation_id="dispatch_public_builder_page_data_source",
        description=(
            "Dispatches the service of the related data_source and returns "
            "the result."
        ),
        request=DispatchDataSourceRequestSerializer,
        responses={
            404: get_error_schema(
                [
                    "ERROR_DATA_SOURCE_DOES_NOT_EXIST",
                    "ERROR_ELEMENT_DOES_NOT_EXIST",
                    "ERROR_DATA_SOURCE_REFINEMENT_FORBIDDEN",
                    "ERROR_SERVICE_IMPROPERLY_CONFIGURED",
                    "ERROR_SERVICE_INVALID_DISPATCH_CONTEXT",
                    "ERROR_SERVICE_INVALID_DISPATCH_CONTEXT_CONTENT",
                    "ERROR_SERVICE_UNEXPECTED_DISPATCH_ERROR",
                    "ERROR_SERVICE_SORT_PROPERTY_DOES_NOT_EXIST",
                    "ERROR_SERVICE_FILTER_PROPERTY_DOES_NOT_EXIST",
                    "ERROR_DATA_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DoesNotExist: ERROR_DATA_DOES_NOT_EXIST,
            ElementDoesNotExist: ERROR_ELEMENT_DOES_NOT_EXIST,
            DataSourceDoesNotExist: ERROR_DATA_SOURCE_DOES_NOT_EXIST,
            DataSourceRefinementForbidden: ERROR_DATA_SOURCE_REFINEMENT_FORBIDDEN,
            ServiceSortPropertyDoesNotExist: ERROR_SERVICE_SORT_PROPERTY_DOES_NOT_EXIST,
            ServiceFilterPropertyDoesNotExist: ERROR_SERVICE_FILTER_PROPERTY_DOES_NOT_EXIST,
            ServiceImproperlyConfiguredDispatchException: ERROR_SERVICE_IMPROPERLY_CONFIGURED,
            InvalidContextDispatchException: ERROR_SERVICE_INVALID_DISPATCH_CONTEXT,
            InvalidContextContentDispatchException: ERROR_SERVICE_INVALID_DISPATCH_CONTEXT_CONTENT,
            UnexpectedDispatchException: ERROR_SERVICE_UNEXPECTED_DISPATCH_ERROR,
        }
    )
    def post(self, request, data_source_id: int):
        """
        Call the given data_source related service dispatch method.
        """

        data_source = DataSourceHandler().get_data_source(data_source_id)

        dispatch_context = BuilderDispatchContext(
            request,
            data_source.page,
            only_expose_public_allowed_properties=True,
        )
        response = DataSourceService().dispatch_data_source(
            request.user, data_source, dispatch_context
        )

        return Response(response)


class PublicDispatchDataSourcesView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="page_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The page we want to dispatch the data source for.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder data sources"],
        operation_id="dispatch_public_builder_page_data_sources",
        description="Dispatches the service of the related page data_sources",
        responses={
            404: get_error_schema(
                [
                    "ERROR_DATA_DOES_NOT_EXIST",
                    "ERROR_PAGE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
            DoesNotExist: ERROR_DATA_DOES_NOT_EXIST,
        }
    )
    def post(self, request, page_id: str):
        """
        Call the given data_source related service dispatch method.
        """

        page = PageHandler().get_page(int(page_id))
        dispatch_context = BuilderDispatchContext(
            request, page, only_expose_public_allowed_properties=True
        )
        service_contents = DataSourceService().dispatch_page_data_sources(
            request.user, page, dispatch_context
        )

        responses = {}

        for service_id, content in service_contents.items():
            if isinstance(content, Exception):
                _, error, detail = apply_exception_mapping(
                    {
                        DataSourceDoesNotExist: ERROR_DATA_SOURCE_DOES_NOT_EXIST,
                        ServiceImproperlyConfiguredDispatchException: ERROR_SERVICE_IMPROPERLY_CONFIGURED,
                        InvalidContextDispatchException: ERROR_SERVICE_INVALID_DISPATCH_CONTEXT,
                        InvalidContextContentDispatchException: ERROR_SERVICE_INVALID_DISPATCH_CONTEXT_CONTENT,
                        UnexpectedDispatchException: ERROR_SERVICE_UNEXPECTED_DISPATCH_ERROR,
                        DoesNotExist: ERROR_DATA_DOES_NOT_EXIST,
                        PermissionException: ERROR_PERMISSION_DENIED,
                    },
                    content,
                    with_fallback=True,
                )
                responses[service_id] = {"_error": error, "detail": detail}
            else:
                responses[service_id] = content

        return Response(responses)
