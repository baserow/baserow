from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_data_custom_fields
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.services.errors import ERROR_SERVICE_INVALID_TYPE
from baserow.api.utils import (
    CustomFieldRegistryMappingSerializer,
    DiscriminatorCustomFieldsMappingSerializer,
)
from baserow.contrib.dashboard.api.errors import ERROR_DASHBOARD_DOES_NOT_EXIST
from baserow.contrib.dashboard.data_sources.actions import (
    UpdateDashboardDataSourceActionType,
)
from baserow.contrib.dashboard.data_sources.dispatch_context import (
    DashboardDispatchContext,
)
from baserow.contrib.dashboard.data_sources.exceptions import (
    DashboardDataSourceDoesNotExist,
    DashboardDataSourceImproperlyConfigured,
    ServiceConfigurationNotAllowed,
)
from baserow.contrib.dashboard.data_sources.handler import DashboardDataSourceHandler
from baserow.contrib.dashboard.data_sources.service import DashboardDataSourceService
from baserow.contrib.dashboard.exceptions import DashboardDoesNotExist
from baserow.core.services.exceptions import (
    DoesNotExist,
    InvalidServiceTypeDispatchSource,
    ServiceImproperlyConfiguredDispatchException,
    ServiceTypeDoesNotExist,
)
from baserow.core.services.registries import service_type_registry

from .errors import (
    ERROR_DASHBOARD_DATA_DOES_NOT_EXIST,
    ERROR_DASHBOARD_DATA_SOURCE_CANNOT_USE_SERVICE_TYPE,
    ERROR_DASHBOARD_DATA_SOURCE_DOES_NOT_EXIST,
    ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED,
    ERROR_SERVICE_CONFIGURATION_NOT_ALLOWED,
)
from .serializers import (
    DashboardDataSourceSerializer,
    UpdateDashboardDataSourceSerializer,
)


class DashboardDataSourcesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="dashboard_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the data sources of the dashboard "
                "related to the provided Id.",
            )
        ],
        tags=["Dashboard data sources"],
        operation_id="list_dashboard_data_sources",
        description=(
            "Lists all the data sources of the dashboard if "
            "the user has access to the related dashboard's workspace."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                service_type_registry, DashboardDataSourceSerializer, many=True
            ),
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(["ERROR_DASHBOARD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            DashboardDoesNotExist: ERROR_DASHBOARD_DOES_NOT_EXIST,
        }
    )
    def get(self, request, dashboard_id):
        """
        Responds with a list of serialized data sources that belong to the dashboard
        if the user has access to it.
        """

        data_sources = DashboardDataSourceService().get_data_sources(
            request.user, dashboard_id
        )

        data = [
            (
                service_type_registry.get_serializer(
                    data_source.service,
                    DashboardDataSourceSerializer,
                    context={"data_source": data_source},
                ).data
            )
            for data_source in data_sources
        ]
        return Response(data)


class DashboardDataSourceView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="data_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the dashboard data source.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Dashboard data sources"],
        operation_id="update_dashboard_data_source",
        description="Updates an existing dashboard data source.",
        request=CustomFieldRegistryMappingSerializer(
            service_type_registry,
            UpdateDashboardDataSourceSerializer,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                service_type_registry, DashboardDataSourceSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_SERVICE_INVALID_TYPE",
                    "ERROR_SERVICE_CONFIGURATION_NOT_ALLOWED",
                    "ERROR_DASHBOARD_DATA_SOURCE_CANNOT_USE_SERVICE_TYPE",
                ]
            ),
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
            404: get_error_schema(
                [
                    "ERROR_DASHBOARD_DATA_SOURCE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DashboardDataSourceDoesNotExist: ERROR_DASHBOARD_DATA_SOURCE_DOES_NOT_EXIST,
            InvalidServiceTypeDispatchSource: ERROR_DASHBOARD_DATA_SOURCE_CANNOT_USE_SERVICE_TYPE,
            ServiceTypeDoesNotExist: ERROR_SERVICE_INVALID_TYPE,
            ServiceConfigurationNotAllowed: ERROR_SERVICE_CONFIGURATION_NOT_ALLOWED,
        }
    )
    def patch(self, request, data_source_id: int):
        """
        Update a dashboard data source.
        """

        service_type = None
        request_service_type = None
        if "type" in request.data:
            request_type_name = request.data["type"]
            request_service_type = service_type_registry.get(request_type_name)

        data_source = DashboardDataSourceHandler().get_data_source(data_source_id)
        original_service_type = service_type_registry.get_by_model(
            data_source.service.specific_class
        )

        service_type = (
            request_service_type
            if request_service_type is not None
            else original_service_type
        )

        data = validate_data_custom_fields(
            service_type.type,
            service_type_registry,
            request.data,
            base_serializer_class=UpdateDashboardDataSourceSerializer,
            return_validated=True,
        )

        data_source_updated = UpdateDashboardDataSourceActionType.do(
            request.user, data_source_id, service_type, data
        )
        serializer = service_type_registry.get_serializer(
            data_source_updated.service,
            DashboardDataSourceSerializer,
            context={"data_source": data_source_updated},
        )
        return Response(serializer.data)


class DispatchDashboardDataSourceView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="data_source_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the data source you want to call the dispatch "
                "for",
            ),
        ],
        tags=["Dashboard data sources"],
        operation_id="dispatch_dashboard_data_source",
        description=(
            "Dispatches the service of the related data source and returns "
            "the result."
        ),
        request=None,
        responses={
            404: get_error_schema(
                [
                    "ERROR_DASHBOARD_DATA_SOURCE_DOES_NOT_EXIST",
                    "ERROR_DASHBOARD_DATA_DOES_NOT_EXIST",
                ]
            ),
            400: get_error_schema(
                [
                    "ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED",
                ]
            ),
            401: get_error_schema(["ERROR_PERMISSION_DENIED"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DashboardDataSourceDoesNotExist: ERROR_DASHBOARD_DATA_SOURCE_DOES_NOT_EXIST,
            DashboardDataSourceImproperlyConfigured: ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED,
            ServiceImproperlyConfiguredDispatchException: ERROR_DASHBOARD_DATA_SOURCE_IMPROPERLY_CONFIGURED,
            DoesNotExist: ERROR_DASHBOARD_DATA_DOES_NOT_EXIST,
        }
    )
    def post(self, request, data_source_id: int):
        """
        Call the given data source related service dispatch method.
        """

        dispatch_context = DashboardDispatchContext(request)
        response = DashboardDataSourceService().dispatch_data_source(
            request.user, data_source_id, dispatch_context
        )
        return Response(response)
