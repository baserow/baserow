from typing import Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    require_request_data_type,
    validate_body,
    validate_body_custom_fields,
)
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
    CustomFieldRegistryMappingSerializer,
    DiscriminatorCustomFieldsMappingSerializer,
    apply_exception_mapping,
    validate_data,
    validate_data_custom_fields,
)
from baserow.contrib.builder.api.data_sources.errors import (
    ERROR_DATA_DOES_NOT_EXIST,
    ERROR_DATA_SOURCE_CANNOT_USE_SERVICE_TYPE,
    ERROR_DATA_SOURCE_DOES_NOT_EXIST,
    ERROR_DATA_SOURCE_NAME_NOT_UNIQUE,
    ERROR_DATA_SOURCE_NOT_IN_SAME_PAGE,
    ERROR_DATA_SOURCE_REFINEMENT_FORBIDDEN,
)
from baserow.contrib.builder.api.data_sources.serializers import (
    BaseUpdateDataSourceSerializer,
    CreateDataSourceSerializer,
    DataSourceSerializer,
    DispatchDataSourceRequestSerializer,
    GetRecordIdsSerializer,
    MoveDataSourceSerializer,
    UpdateDataSourceSerializer,
)
from baserow.contrib.builder.api.elements.errors import ERROR_ELEMENT_DOES_NOT_EXIST
from baserow.contrib.builder.api.pages.errors import ERROR_PAGE_DOES_NOT_EXIST
from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.data_sources.exceptions import (
    DataSourceDoesNotExist,
    DataSourceNameNotUniqueError,
    DataSourceNotInSamePage,
    DataSourceRefinementForbidden,
)
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.data_sources.service import DataSourceService
from baserow.contrib.builder.elements.exceptions import ElementDoesNotExist
from baserow.contrib.builder.pages.exceptions import PageDoesNotExist
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.contrib.builder.pages.models import Page
from baserow.core.exceptions import PermissionException
from baserow.core.services.exceptions import (
    DoesNotExist,
    InvalidContextContentDispatchException,
    InvalidContextDispatchException,
    InvalidServiceTypeDispatchSource,
    ServiceFilterPropertyDoesNotExist,
    ServiceImproperlyConfiguredDispatchException,
    ServiceSortPropertyDoesNotExist,
    UnexpectedDispatchException,
)
from baserow.core.services.registries import service_type_registry


class DataSourcesView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="page_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the data_sources of the page related to the "
                "provided Id.",
            )
        ],
        tags=["Builder data sources"],
        operation_id="list_builder_page_data_sources",
        description=(
            "Lists all the data_sources of the page related to the provided parameter if "
            "the user has access to the related builder's workspace. "
            "If the workspace is related to a template, then this endpoint will be "
            "publicly accessible."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                service_type_registry, DataSourceSerializer, many=True
            ),
            404: get_error_schema(["ERROR_PAGE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
        }
    )
    def get(self, request, page_id):
        """
        Responds with a list of serialized data_sources that belong to the page if the
        user has access to that page.
        """

        page = PageHandler().get_page(page_id)

        data_sources = DataSourceService().get_data_sources(request.user, page)

        data = [
            (
                service_type_registry.get_serializer(
                    data_source.service,
                    DataSourceSerializer,
                    context={"data_source": data_source},
                ).data
                if data_source.service
                else DataSourceSerializer(
                    data_source, context={"data_source": data_source}
                ).data
            )
            for data_source in data_sources
        ]
        return Response(data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="page_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a data_source for the builder page related to the "
                "provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder data sources"],
        operation_id="create_builder_page_data_source",
        description="Creates a new builder data_source",
        request=DiscriminatorCustomFieldsMappingSerializer(
            service_type_registry,
            CreateDataSourceSerializer,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                service_type_registry, DataSourceSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_PAGE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
            DataSourceNotInSamePage: ERROR_DATA_SOURCE_NOT_IN_SAME_PAGE,
            DataSourceNameNotUniqueError: ERROR_DATA_SOURCE_NAME_NOT_UNIQUE,
            InvalidServiceTypeDispatchSource: ERROR_DATA_SOURCE_CANNOT_USE_SERVICE_TYPE,
        }
    )
    @validate_body_custom_fields(
        service_type_registry,
        base_serializer_class=CreateDataSourceSerializer,
        allow_empty_type=True,
    )
    def post(self, request, data: Dict, page_id: int):
        """Creates a new data_source."""

        type_name = data.pop("type", None)
        before_id = data.pop("before_id", None)

        page = PageHandler().get_page(page_id)

        before = (
            DataSourceHandler().get_data_source(before_id, specific=False)
            if before_id
            else None
        )

        service_type = service_type_registry.get(type_name) if type_name else None

        data_source = DataSourceService().create_data_source(
            request.user, page, service_type=service_type, before=before, **data
        )

        if data_source.service:
            serializer = service_type_registry.get_serializer(
                data_source.service,
                DataSourceSerializer,
                context={"data_source": data_source},
            )
        else:
            serializer = DataSourceSerializer(
                data_source, context={"data_source": data_source}
            )
        return Response(serializer.data)


class DataSourceView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="data_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the data_source",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder data sources"],
        operation_id="update_builder_page_data_source",
        description="Updates an existing builder data_source.",
        request=CustomFieldRegistryMappingSerializer(
            service_type_registry,
            UpdateDataSourceSerializer,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                service_type_registry, DataSourceSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_DATA_SOURCE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DataSourceDoesNotExist: ERROR_DATA_SOURCE_DOES_NOT_EXIST,
            DataSourceNameNotUniqueError: ERROR_DATA_SOURCE_NAME_NOT_UNIQUE,
            InvalidServiceTypeDispatchSource: ERROR_DATA_SOURCE_CANNOT_USE_SERVICE_TYPE,
        }
    )
    @require_request_data_type(dict)
    def patch(self, request, data_source_id: int):
        """
        Update a data_source.
        """

        data_source = DataSourceHandler().get_data_source_for_update(data_source_id)

        service_type_from_query = None
        service_type_from_service = None
        change_service_type = False
        service_type = None

        page = None
        if "page_id" in request.data:
            page = PageHandler().get_page(
                int(request.data["page_id"]),
                base_queryset=Page.objects.filter(builder=data_source.page.builder),
            )

        # Do we have a service?
        if data_source.service is not None:
            # Yes, let's read the service type from it.
            service_type_from_service = service_type_registry.get_by_model(
                data_source.service.specific
            )
            service_type = service_type_from_service

        # Do we have a service type in the query payload
        if "type" in request.data:
            request_type_name = request.data["type"]
            if request_type_name:
                service_type_from_query = service_type_registry.get(request_type_name)

            # Is this service type different from the current service type?
            if service_type_from_query != service_type_from_service:
                change_service_type = True

        if service_type:
            # We have a service type so either we have a service or a type in the query
            # We need to validate the incoming data against the serializer related to
            # the given type
            data = validate_data_custom_fields(
                service_type.type,
                service_type_registry,
                request.data,
                base_serializer_class=UpdateDataSourceSerializer,
                return_validated=True,
            )

        else:
            # No service nor type, we should validate with the default serializer
            data = validate_data(BaseUpdateDataSourceSerializer, request.data)

        if change_service_type:
            data["new_service_type"] = service_type_from_query

        if page is not None:
            data["page"] = page

        data_source_updated = DataSourceService().update_data_source(
            request.user, data_source, service_type=service_type, **data
        )

        if data_source_updated.service:
            serializer = service_type_registry.get_serializer(
                data_source_updated.service,
                DataSourceSerializer,
                context={"data_source": data_source_updated},
            )
        else:
            serializer = DataSourceSerializer(
                data_source_updated, context={"data_source": data_source_updated}
            )

        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="data_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the data_source",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder data sources"],
        operation_id="delete_builder_page_data_source",
        description="Deletes the data_source related by the given id.",
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_DATA_SOURCE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DataSourceDoesNotExist: ERROR_DATA_SOURCE_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def delete(self, request, data_source_id: int):
        """
        Deletes an data_source.
        """

        data_source = DataSourceHandler().get_data_source_for_update(data_source_id)

        DataSourceService().delete_data_source(request.user, data_source)

        return Response(status=204)


class MoveDataSourceView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="data_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the data_source to move",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder data sources"],
        operation_id="move_builder_page_data_source",
        description=(
            "Moves the data_source in the page before another data_source or at the end of "
            "the page if no before data_source is given. The data_sources must belong to the "
            "same page."
        ),
        request=MoveDataSourceSerializer,
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                service_type_registry, DataSourceSerializer
            ),
            400: get_error_schema(
                ["ERROR_REQUEST_BODY_VALIDATION", "ERROR_DATA_SOURCE_NOT_IN_SAME_PAGE"]
            ),
            404: get_error_schema(
                [
                    "ERROR_DATA_SOURCE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DataSourceDoesNotExist: ERROR_DATA_SOURCE_DOES_NOT_EXIST,
            DataSourceNotInSamePage: ERROR_DATA_SOURCE_NOT_IN_SAME_PAGE,
        }
    )
    @validate_body(MoveDataSourceSerializer)
    def patch(self, request, data: Dict, data_source_id: int):
        """
        Moves the data_source in the page before another data_source or at the end of
        the page if no before data_source is given.
        """

        data_source = DataSourceHandler().get_data_source_for_update(data_source_id)

        before_id = data.get("before_id", None)

        before = None
        if before_id:
            before = DataSourceHandler().get_data_source(before_id, specific=False)

        moved_data_source = DataSourceService().move_data_source(
            request.user, data_source, before
        )

        serializer = service_type_registry.get_serializer(
            moved_data_source.service,
            DataSourceSerializer,
            context={"data_source": moved_data_source},
        )
        return Response(serializer.data)


class DispatchDataSourceView(APIView):
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
        operation_id="dispatch_builder_page_data_source",
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
            DataSourceDoesNotExist: ERROR_DATA_SOURCE_DOES_NOT_EXIST,
            ElementDoesNotExist: ERROR_ELEMENT_DOES_NOT_EXIST,
            DataSourceRefinementForbidden: ERROR_DATA_SOURCE_REFINEMENT_FORBIDDEN,
            ServiceImproperlyConfiguredDispatchException: ERROR_SERVICE_IMPROPERLY_CONFIGURED,
            InvalidContextDispatchException: ERROR_SERVICE_INVALID_DISPATCH_CONTEXT,
            InvalidContextContentDispatchException: ERROR_SERVICE_INVALID_DISPATCH_CONTEXT_CONTENT,
            UnexpectedDispatchException: ERROR_SERVICE_UNEXPECTED_DISPATCH_ERROR,
            ServiceSortPropertyDoesNotExist: ERROR_SERVICE_SORT_PROPERTY_DOES_NOT_EXIST,
            ServiceFilterPropertyDoesNotExist: ERROR_SERVICE_FILTER_PROPERTY_DOES_NOT_EXIST,
            DoesNotExist: ERROR_DATA_DOES_NOT_EXIST,
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
            only_expose_public_allowed_properties=False,
        )

        response = DataSourceService().dispatch_data_source(
            request.user, data_source, dispatch_context
        )

        return Response(response)


class DispatchDataSourcesView(APIView):
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
        operation_id="dispatch_builder_page_data_sources",
        description="Dispatches the service of the related page data_sources",
        request=DispatchDataSourceRequestSerializer,
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
    def post(self, request, page_id: int):
        """
        Call the given data_source related service dispatch method.
        """

        page = PageHandler().get_page(page_id)
        dispatch_context = BuilderDispatchContext(
            request, page, only_expose_public_allowed_properties=False
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


class GetRecordNamesView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="data_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the data_source to find the record names.",
            ),
            OpenApiParameter(
                name="record_ids",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="A comma separated list of the record ids to search for.",
                explode=False,  # This is a single string, not an exploded list
            ),
        ],
        tags=["Builder data sources"],
        operation_id="get_record_names_builder_page_data_source",
        description="Find the record names associated with a given list of record ids.",
        request=GetRecordIdsSerializer,
        responses={
            200: {
                "type": "object",
                "additionalProperties": {
                    "type": "string",
                    "description": "Record name",
                },
                "description": "A dictionary mapping record ids to their names.",
                "example": {
                    "1": "Record name 1",
                    "2": "Record name 2",
                },
            },
            400: get_error_schema(
                [
                    "ERROR_SERVICE_IMPROPERLY_CONFIGURED",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_DATA_SOURCE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            DataSourceDoesNotExist: ERROR_DATA_SOURCE_DOES_NOT_EXIST,
            ServiceImproperlyConfiguredDispatchException: ERROR_SERVICE_IMPROPERLY_CONFIGURED,
        }
    )
    def get(self, request, data_source_id: int):
        # Find the data source corresponding to the given id
        data_source = DataSourceHandler().get_data_source(data_source_id)
        service = data_source.service.specific
        service_type = service.get_type()

        # Check that the data source service is a ListServiceType
        if not service_type.returns_list:
            raise ServiceImproperlyConfiguredDispatchException(
                "This data source does not provide a list service"
            )

        dispatch_context = BuilderDispatchContext(request, data_source.page)

        query = GetRecordIdsSerializer(data=request.query_params)

        if query.is_valid(raise_exception=True):
            record_ids = query.validated_data["record_ids"]
            record_names = service_type.get_record_names(
                service, record_ids, dispatch_context
            )
            return Response(record_names)
