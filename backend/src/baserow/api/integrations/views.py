from typing import Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.applications.errors import (
    ERROR_APPLICATION_DOES_NOT_EXIST,
    ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
)
from baserow.api.decorators import (
    map_exceptions,
    require_request_data_type,
    validate_body,
    validate_body_custom_fields,
)
from baserow.api.integrations.errors import (
    ERROR_INTEGRATION_DOES_NOT_EXIST,
    ERROR_INTEGRATION_NOT_IN_SAME_APPLICATION,
)
from baserow.api.integrations.serializers import (
    CreateIntegrationSerializer,
    IntegrationSerializer,
    MoveIntegrationSerializer,
    UpdateIntegrationSerializer,
)
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.utils import (
    CustomFieldRegistryMappingSerializer,
    DiscriminatorCustomFieldsMappingSerializer,
    type_from_data_or_registry,
    validate_data_custom_fields,
)
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    ApplicationOperationNotSupported,
)
from baserow.core.handler import CoreHandler
from baserow.core.integrations.exceptions import (
    IntegrationDoesNotExist,
    IntegrationNotInSameApplication,
)
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService


class IntegrationsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the integrations of the application related "
                "to the provided Id.",
            )
        ],
        tags=["Integrations"],
        operation_id="list_application_integrations",
        description=(
            "Lists all the integrations of the application related to the provided "
            "parameter if the user has access to the related application's workspace. "
            "If the workspace is related to a template, then this endpoint will be "
            "publicly accessible."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                integration_type_registry, IntegrationSerializer, many=True
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
        }
    )
    def get(self, request, application_id):
        """
        Responds with a list of serialized integrations that belong to the application
        if the user has access to that application.
        """

        application = CoreHandler().get_application(application_id)

        integrations = IntegrationService().get_integrations(request.user, application)

        data = [
            integration_type_registry.get_serializer(
                integration, IntegrationSerializer
            ).data
            for integration in integrations
        ]

        return Response(data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="application_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates an integration for the application related to the "
                "provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Integrations"],
        operation_id="create_application_integration",
        description="Creates a new integration",
        request=DiscriminatorCustomFieldsMappingSerializer(
            integration_type_registry,
            CreateIntegrationSerializer,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                integration_type_registry, IntegrationSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            ApplicationOperationNotSupported: ERROR_APPLICATION_OPERATION_NOT_SUPPORTED,
        }
    )
    @validate_body_custom_fields(
        integration_type_registry,
        base_serializer_class=CreateIntegrationSerializer,
    )
    def post(self, request, data: Dict, application_id: int):
        """Creates a new integration."""

        type_name = data.pop("type")
        application = CoreHandler().get_application(application_id)

        before_id = data.pop("before_id", None)
        before = IntegrationHandler().get_integration(before_id) if before_id else None

        integration_type = integration_type_registry.get(type_name)
        integration = IntegrationService().create_integration(
            request.user, integration_type, application, before=before, **data
        )

        serializer = integration_type_registry.get_serializer(
            integration, IntegrationSerializer
        )
        return Response(serializer.data)


class IntegrationView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="integration_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the integration",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Integrations"],
        operation_id="update_application_integration",
        description="Updates an existing integration.",
        request=CustomFieldRegistryMappingSerializer(
            integration_type_registry,
            UpdateIntegrationSerializer,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                integration_type_registry, IntegrationSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_INTEGRATION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            IntegrationDoesNotExist: ERROR_INTEGRATION_DOES_NOT_EXIST,
        }
    )
    @require_request_data_type(dict)
    def patch(self, request, integration_id: int):
        """
        Update an integration.
        """

        integration = IntegrationHandler().get_integration_for_update(integration_id)
        integration_type = type_from_data_or_registry(
            request.data, integration_type_registry, integration
        )
        data = validate_data_custom_fields(
            integration_type.type,
            integration_type_registry,
            request.data,
            base_serializer_class=UpdateIntegrationSerializer,
        )

        integration_updated = IntegrationService().update_integration(
            request.user, integration, **data
        )

        serializer = integration_type_registry.get_serializer(
            integration_updated, IntegrationSerializer
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="integration_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the integration",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Integrations"],
        operation_id="delete_application_integration",
        description="Deletes the integration related by the given id.",
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_INTEGRATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            IntegrationDoesNotExist: ERROR_INTEGRATION_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def delete(self, request, integration_id: int):
        """
        Deletes an integration.
        """

        integration = IntegrationHandler().get_integration_for_update(integration_id)

        IntegrationService().delete_integration(request.user, integration)

        return Response(status=204)


class MoveIntegrationView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="integration_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the integration to move",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Integrations"],
        operation_id="move_application_integration",
        description=(
            "Moves the integration in the application before another integration or at "
            "the end of the application if no before integration is given. "
            "The integrations must belong to the same application."
        ),
        request=MoveIntegrationSerializer,
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                integration_type_registry, IntegrationSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_INTEGRATION_NOT_IN_SAME_APPLICATION",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_INTEGRATION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            IntegrationDoesNotExist: ERROR_INTEGRATION_DOES_NOT_EXIST,
            IntegrationNotInSameApplication: ERROR_INTEGRATION_NOT_IN_SAME_APPLICATION,
        }
    )
    @validate_body(MoveIntegrationSerializer)
    def patch(self, request, data: Dict, integration_id: int):
        """
        Moves the integration in the application before another integration or at the
        end of the application if no before integration is given.
        """

        integration = IntegrationHandler().get_integration_for_update(integration_id)

        before_id = data.get("before_id", None)

        before = None
        if before_id:
            before = IntegrationHandler().get_integration(before_id)

        moved_integration = IntegrationService().move_integration(
            request.user, integration, before
        )

        serializer = integration_type_registry.get_serializer(
            moved_integration, IntegrationSerializer
        )
        return Response(serializer.data)
