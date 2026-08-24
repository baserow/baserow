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
    validate_body,
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
from baserow.contrib.database.api.rows.errors import ERROR_ROW_DOES_NOT_EXIST
from baserow.contrib.database.api.workflow_actions.errors import (
    ERROR_WORKFLOW_ACTION_DISPATCH_FAILED,
    ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS,
    ERROR_WORKFLOW_ACTION_DOES_NOT_EXIST,
    ERROR_WORKFLOW_ACTION_NOT_IN_FIELD,
)
from baserow.contrib.database.api.workflow_actions.serializers import (
    CreateDatabaseWorkflowActionSerializer,
    DatabaseWorkflowActionSerializer,
    DispatchWorkflowActionsResponseSerializer,
    DispatchWorkflowActionsSerializer,
    OrderWorkflowActionsSerializer,
    UpdateDatabaseWorkflowActionSerializer,
)
from baserow.contrib.database.application_types import DatabaseApplicationType
from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionDispatchError,
    WorkflowActionDispatchInProgress,
    WorkflowActionNotInField,
)
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
from baserow.core.feature_flags import FF_BUTTON_FIELD, feature_flag_is_enabled
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
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
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
        serializer_class_context={"application_type": DatabaseApplicationType},
    )
    def post(self, request, data: Dict, field_id: int):
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

        type_name = data.pop("type")
        workflow_action_type = database_workflow_action_type_registry.get(type_name)
        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)

        workflow_action = DatabaseWorkflowActionService().create_workflow_action(
            request.user, workflow_action_type, field, **data
        )

        serializer = database_workflow_action_type_registry.get_serializer(
            workflow_action,
            DatabaseWorkflowActionSerializer,
            context={"user": request.user},
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
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
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
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)

        workflow_actions = DatabaseWorkflowActionService().get_workflow_actions(
            request.user, field
        )

        data = [
            database_workflow_action_type_registry.get_serializer(
                workflow_action,
                DatabaseWorkflowActionSerializer,
                context={"user": request.user},
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
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
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
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

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
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
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
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

        # Locked for the request: a type change swaps the action's own row, so
        # a concurrent update must not read it half way through.
        workflow_action = (
            DatabaseWorkflowActionHandler().get_workflow_action_for_update(
                workflow_action_id
            )
        )
        workflow_action_type = type_from_data_or_registry(
            request.data, database_workflow_action_type_registry, workflow_action
        )
        data = validate_data_custom_fields(
            workflow_action_type.type,
            database_workflow_action_type_registry,
            request.data,
            base_serializer_class=UpdateDatabaseWorkflowActionSerializer,
            serializer_class_context={"application_type": DatabaseApplicationType},
            partial=True,
        )

        workflow_action_updated = (
            DatabaseWorkflowActionService().update_workflow_action(
                request.user, workflow_action, **data
            )
        )

        serializer = database_workflow_action_type_registry.get_serializer(
            workflow_action_updated,
            DatabaseWorkflowActionSerializer,
            context={"user": request.user},
        )
        return Response(serializer.data)


class OrderDatabaseWorkflowActionsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The button field the workflow actions belong to.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="order_database_field_workflow_actions",
        description="Apply a new order to the workflow actions of a button field.",
        request=OrderWorkflowActionsSerializer,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_WORKFLOW_ACTION_NOT_IN_FIELD",
                ]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkflowActionNotInField: ERROR_WORKFLOW_ACTION_NOT_IN_FIELD,
        }
    )
    @validate_body(OrderWorkflowActionsSerializer)
    def post(self, request, data: Dict, field_id: int):
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)

        DatabaseWorkflowActionService().order_workflow_actions(
            request.user, field, data["workflow_action_ids"]
        )

        return Response(status=204)


class DispatchDatabaseWorkflowActionsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Runs the button field's actions, in order, for the "
                "provided row.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="dispatch_database_field_workflow_actions",
        description=(
            "Runs every workflow action of a button field, in order, for the "
            "given row, and returns one result per action."
        ),
        request=DispatchWorkflowActionsSerializer,
        responses={
            200: DispatchWorkflowActionsResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_WORKFLOW_ACTION_DISPATCH_FAILED",
                ]
            ),
            403: get_error_schema(["ERROR_FEATURE_DISABLED"]),
            404: get_error_schema(
                [
                    "ERROR_FIELD_DOES_NOT_EXIST",
                    "ERROR_ROW_DOES_NOT_EXIST",
                ]
            ),
            409: get_error_schema(["ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS"]),
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            WorkflowActionDispatchInProgress: ERROR_WORKFLOW_ACTION_DISPATCH_IN_PROGRESS,
            WorkflowActionDispatchError: ERROR_WORKFLOW_ACTION_DISPATCH_FAILED,
        }
    )
    @validate_body(DispatchWorkflowActionsSerializer)
    def post(self, request, data: Dict, field_id: int):
        feature_flag_is_enabled(FF_BUTTON_FIELD, raise_if_disabled=True)

        field = FieldHandler().get_field(field_id, base_queryset=ButtonField.objects)
        row = RowHandler().get_row(request.user, field.table, data["row_id"])

        dispatch = DatabaseWorkflowActionService().dispatch_workflow_actions(
            request.user, field, row
        )

        # Only a client action reads a result, and naming the fields costs a
        # table model per action. An action that returned no row, a delete for
        # instance, has no names to give either.
        names_wanted = bool(dispatch.client_actions)

        # Naming the fields builds the table model, so two actions against the
        # same table would otherwise build it twice for the same names.
        field_names_by_table = {}

        def field_names_for(dispatched):
            if not names_wanted or not isinstance(dispatched.result.data, dict):
                return {}
            workflow_action = dispatched.workflow_action
            table_id = getattr(
                getattr(workflow_action, "service", None), "table_id", None
            )
            if table_id is None:
                return workflow_action.get_type().get_result_field_names(
                    workflow_action
                )
            if table_id not in field_names_by_table:
                field_names_by_table[table_id] = (
                    workflow_action.get_type().get_result_field_names(workflow_action)
                )
            return field_names_by_table[table_id]

        results = [
            {
                "workflow_action_id": dispatched.workflow_action.id,
                # Every action runs synchronously inside the request. The field
                # is here so an async one can report "dispatched" later.
                "status": "completed",
                "data": dispatched.result.data,
                "field_names": field_names_for(dispatched),
            }
            for dispatched in dispatch.dispatched
        ]

        return Response(
            {
                "results": results,
                "client_actions": [
                    database_workflow_action_type_registry.get_serializer(
                        workflow_action,
                        DatabaseWorkflowActionSerializer,
                        context={"user": request.user},
                    ).data
                    for workflow_action in dispatch.client_actions
                ],
            }
        )
