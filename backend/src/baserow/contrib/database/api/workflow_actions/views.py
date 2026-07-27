from typing import Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    require_request_data_type,
    validate_body_custom_fields,
)
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.utils import (
    CustomFieldRegistryMappingSerializer,
    DiscriminatorCustomFieldsMappingSerializer,
    type_from_data_or_registry,
    validate_data_custom_fields,
)
from baserow.contrib.database.api.fields.errors import ERROR_FIELD_DOES_NOT_EXIST
from baserow.contrib.database.api.workflow_actions.errors import (
    ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST,
)
from baserow.contrib.database.api.workflow_actions.serializers import (
    CreateDatabaseWorkflowActionSerializer,
    DatabaseWorkflowActionSerializer,
    UpdateDatabaseWorkflowActionSerializer,
)
from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.workflow_actions.handler import (
    DatabaseWorkflowActionHandler,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.service import (
    DatabaseWorkflowActionService,
)
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.workflow_actions.exceptions import WorkflowActionDoesNotExist


class DatabaseWorkflowActionsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a workflow action for the button field related "
                "to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="create_database_field_workflow_action",
        description="Creates a new database workflow action.",
        request=DiscriminatorCustomFieldsMappingSerializer(
            database_workflow_action_type_registry,
            CreateDatabaseWorkflowActionSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                database_workflow_action_type_registry,
                DatabaseWorkflowActionSerializer,
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_USER_NOT_IN_GROUP",
                ]
            ),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body_custom_fields(
        database_workflow_action_type_registry,
        base_serializer_class=CreateDatabaseWorkflowActionSerializer,
    )
    def post(self, request, data: Dict, field_id: int):
        type_name = data.pop("type")
        workflow_action_type = database_workflow_action_type_registry.get(type_name)
        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)

        workflow_action = DatabaseWorkflowActionService().create_workflow_action(
            request.user, workflow_action_type, field, **data
        )

        serializer = database_workflow_action_type_registry.get_serializer(
            workflow_action, DatabaseWorkflowActionSerializer
        )

        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the workflow actions of the button field "
                "related to the provided Id.",
            )
        ],
        tags=["Database table fields"],
        operation_id="list_database_field_workflow_actions",
        description=(
            "Lists all the workflow actions of the button field related to the "
            "provided parameter if the user has access to the related "
            "database's workspace."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                database_workflow_action_type_registry,
                DatabaseWorkflowActionSerializer,
                many=True,
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, field_id: int):
        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)

        workflow_actions = DatabaseWorkflowActionService().get_workflow_actions(
            request.user, field
        )

        data = [
            database_workflow_action_type_registry.get_serializer(
                workflow_action, DatabaseWorkflowActionSerializer
            ).data
            for workflow_action in workflow_actions
        ]

        return Response(data)


class DatabaseWorkflowActionView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_action_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workflow action.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="delete_database_field_workflow_action",
        description="Deletes the workflow action related by the given id.",
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_USER_NOT_IN_GROUP",
                ]
            ),
            404: get_error_schema(["ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkflowActionDoesNotExist: ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, workflow_action_id: int):
        workflow_action = DatabaseWorkflowActionHandler().get_workflow_action(
            workflow_action_id
        )

        DatabaseWorkflowActionService().delete_workflow_action(
            request.user, workflow_action
        )

        return Response(status=204)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_action_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the workflow action.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="update_database_field_workflow_action",
        description="Updates an existing database workflow action.",
        request=CustomFieldRegistryMappingSerializer(
            database_workflow_action_type_registry,
            UpdateDatabaseWorkflowActionSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                database_workflow_action_type_registry,
                DatabaseWorkflowActionSerializer,
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_USER_NOT_IN_GROUP",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            WorkflowActionDoesNotExist: ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @require_request_data_type(dict)
    def patch(self, request, workflow_action_id: int):
        workflow_action = DatabaseWorkflowActionHandler().get_workflow_action(
            workflow_action_id
        )
        workflow_action_type = type_from_data_or_registry(
            request.data, database_workflow_action_type_registry, workflow_action
        )
        data = validate_data_custom_fields(
            workflow_action_type.type,
            database_workflow_action_type_registry,
            request.data,
            base_serializer_class=UpdateDatabaseWorkflowActionSerializer,
            partial=True,
        )

        workflow_action_updated = (
            DatabaseWorkflowActionService().update_workflow_action(
                request.user, workflow_action, **data
            )
        )

        serializer = database_workflow_action_type_registry.get_serializer(
            workflow_action_updated, DatabaseWorkflowActionSerializer
        )
        return Response(serializer.data)
