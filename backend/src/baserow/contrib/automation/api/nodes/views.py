from typing import Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    require_request_data_type,
    validate_body,
)
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.utils import (
    DiscriminatorCustomFieldsMappingSerializer,
    type_from_data_or_registry,
    validate_data_custom_fields,
)
from baserow.contrib.automation.api.nodes.errors import (
    ERROR_AUTOMATION_FIRST_NODE_MUST_BE_TRIGGER,
    ERROR_AUTOMATION_NODE_DOES_NOT_EXIST,
    ERROR_AUTOMATION_NODE_MISCONFIGURED_SERVICE,
    ERROR_AUTOMATION_NODE_NOT_DELETABLE,
    ERROR_AUTOMATION_NODE_NOT_IN_WORKFLOW,
    ERROR_AUTOMATION_NODE_NOT_MOVABLE,
    ERROR_AUTOMATION_NODE_NOT_REPLACEABLE,
    ERROR_AUTOMATION_NODE_REFERENCE_NODE_INVALID,
    ERROR_AUTOMATION_NODE_SIMULATE_DISPATCH,
    ERROR_AUTOMATION_TRIGGER_ALREADY_EXISTS,
    ERROR_AUTOMATION_TRIGGER_MUST_BE_FIRST_NODE,
    ERROR_AUTOMATION_UNEXPECTED_ERROR,
)
from baserow.contrib.automation.api.nodes.serializers import (
    AutomationNodeSerializer,
    CreateAutomationNodeSerializer,
    MoveAutomationNodeSerializer,
    ReplaceAutomationNodeSerializer,
    UpdateAutomationNodeSerializer,
)
from baserow.contrib.automation.api.workflows.errors import (
    ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
)
from baserow.contrib.automation.nodes.actions import (
    CreateAutomationNodeActionType,
    DeleteAutomationNodeActionType,
    DuplicateAutomationNodeActionType,
    MoveAutomationNodeActionType,
    ReplaceAutomationNodeActionType,
    UpdateAutomationNodeActionType,
)
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeDoesNotExist,
    AutomationNodeError,
    AutomationNodeFirstNodeMustBeTrigger,
    AutomationNodeMisconfiguredService,
    AutomationNodeNotDeletable,
    AutomationNodeNotInWorkflow,
    AutomationNodeNotMovable,
    AutomationNodeNotReplaceable,
    AutomationNodeReferenceNodeInvalid,
    AutomationNodeSimulateDispatchError,
    AutomationNodeTriggerAlreadyExists,
    AutomationNodeTriggerMustBeFirstNode,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.nodes.service import AutomationNodeService
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist,
)
from baserow.contrib.automation.workflows.service import AutomationWorkflowService

AUTOMATION_NODES_TAG = "Automation nodes"


class AutomationNodesView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates an automation node for the associated workflow.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_NODES_TAG],
        operation_id="create_automation_node",
        description="Creates a new automation workflow node",
        request=DiscriminatorCustomFieldsMappingSerializer(
            automation_node_type_registry,
            CreateAutomationNodeSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                automation_node_type_registry, AutomationNodeSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
            AutomationNodeReferenceNodeInvalid: ERROR_AUTOMATION_NODE_REFERENCE_NODE_INVALID,
            AutomationNodeDoesNotExist: ERROR_AUTOMATION_NODE_DOES_NOT_EXIST,
            AutomationNodeTriggerAlreadyExists: ERROR_AUTOMATION_TRIGGER_ALREADY_EXISTS,
            AutomationNodeFirstNodeMustBeTrigger: ERROR_AUTOMATION_FIRST_NODE_MUST_BE_TRIGGER,
            AutomationNodeTriggerMustBeFirstNode: ERROR_AUTOMATION_TRIGGER_MUST_BE_FIRST_NODE,
            AutomationNodeError: ERROR_AUTOMATION_UNEXPECTED_ERROR,
        }
    )
    @validate_body(CreateAutomationNodeSerializer)
    def post(self, request, data: Dict, workflow_id: int):
        type_name = data.pop("type")
        node_type = automation_node_type_registry.get(type_name)
        workflow = AutomationWorkflowService().get_workflow(request.user, workflow_id)

        node = CreateAutomationNodeActionType.do(
            request.user, node_type, workflow, data
        )

        serializer = automation_node_type_registry.get_serializer(
            node, AutomationNodeSerializer
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the nodes related to a specific workflow.",
            )
        ],
        tags=[AUTOMATION_NODES_TAG],
        operation_id="list_nodes",
        description=(
            "Lists all the nodes of the workflow related to the provided parameter "
            "if the user has access to the related automation's workspace. "
            "If the workspace is related to a template, then this endpoint will be "
            "publicly accessible."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                automation_node_type_registry,
                AutomationNodeSerializer,
                many=True,
            ),
            404: get_error_schema(["ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
        }
    )
    def get(self, request, workflow_id: int):
        workflow = AutomationWorkflowService().get_workflow(request.user, workflow_id)

        nodes = AutomationNodeService().get_nodes(request.user, workflow)

        data = [
            automation_node_type_registry.get_serializer(
                node, AutomationNodeSerializer
            ).data
            for node in nodes
        ]

        return Response(data)


class AutomationNodeView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="node_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the node to update.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_NODES_TAG],
        operation_id="update_automation_node",
        description="Updates an existing automation node.",
        request=DiscriminatorCustomFieldsMappingSerializer(
            automation_node_type_registry,
            UpdateAutomationNodeSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                automation_node_type_registry, AutomationNodeSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_AUTOMATION_NODE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationNodeDoesNotExist: ERROR_AUTOMATION_NODE_DOES_NOT_EXIST,
            AutomationNodeMisconfiguredService: ERROR_AUTOMATION_NODE_MISCONFIGURED_SERVICE,
        }
    )
    @require_request_data_type(dict)
    def patch(self, request, node_id: int):
        node = AutomationNodeHandler().get_node(node_id)
        node_type = type_from_data_or_registry(
            request.data, automation_node_type_registry, node
        )

        data = validate_data_custom_fields(
            node_type.type,
            automation_node_type_registry,
            request.data,
            base_serializer_class=UpdateAutomationNodeSerializer,
            partial=True,
            return_validated=True,
        )

        node = UpdateAutomationNodeActionType.do(request.user, node_id, data)

        serializer = automation_node_type_registry.get_serializer(
            node, AutomationNodeSerializer
        )

        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="node_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the node to delete.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_NODES_TAG],
        operation_id="delete_automation_node",
        description="Deletes an existing automation node.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
            404: get_error_schema(["ERROR_AUTOMATION_NODE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationNodeDoesNotExist: ERROR_AUTOMATION_NODE_DOES_NOT_EXIST,
            AutomationNodeNotDeletable: ERROR_AUTOMATION_NODE_NOT_DELETABLE,
            AutomationNodeFirstNodeMustBeTrigger: ERROR_AUTOMATION_TRIGGER_MUST_BE_FIRST_NODE,
            AutomationNodeError: ERROR_AUTOMATION_UNEXPECTED_ERROR,
        }
    )
    @transaction.atomic
    def delete(self, request, node_id: int):
        node = AutomationNodeService().get_node(request.user, node_id)

        node.get_type().before_delete(node)

        DeleteAutomationNodeActionType.do(request.user, node_id)

        return Response(status=204)


class DuplicateAutomationNodeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="node_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The node that is to be duplicated.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_NODES_TAG],
        operation_id="duplicate_automation_node",
        description="Duplicate a node of a workflow.",
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                automation_node_type_registry, AutomationNodeSerializer
            ),
            404: get_error_schema(
                [
                    "ERROR_AUTOMATION_NODE_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationNodeDoesNotExist: ERROR_AUTOMATION_NODE_DOES_NOT_EXIST,
            AutomationNodeTriggerMustBeFirstNode: ERROR_AUTOMATION_TRIGGER_MUST_BE_FIRST_NODE,
            AutomationNodeTriggerAlreadyExists: ERROR_AUTOMATION_TRIGGER_ALREADY_EXISTS,
            AutomationNodeFirstNodeMustBeTrigger: ERROR_AUTOMATION_FIRST_NODE_MUST_BE_TRIGGER,
            AutomationNodeError: ERROR_AUTOMATION_UNEXPECTED_ERROR,
        }
    )
    def post(self, request, node_id: int):
        """Duplicate an automation node."""

        duplicated_node = DuplicateAutomationNodeActionType.do(request.user, node_id)
        return Response(
            automation_node_type_registry.get_serializer(
                duplicated_node, AutomationNodeSerializer
            ).data
        )


class ReplaceAutomationNodeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="node_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The node that is to be replaced.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_NODES_TAG],
        operation_id="replace_automation_node",
        description="Replace a node in a workflow with one of a new type.",
        request=ReplaceAutomationNodeSerializer,
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                automation_node_type_registry, AutomationNodeSerializer
            ),
            400: get_error_schema(["ERROR_AUTOMATION_NODE_NOT_REPLACEABLE"]),
            404: get_error_schema(["ERROR_AUTOMATION_NODE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationNodeDoesNotExist: ERROR_AUTOMATION_NODE_DOES_NOT_EXIST,
            AutomationNodeNotReplaceable: ERROR_AUTOMATION_NODE_NOT_REPLACEABLE,
            AutomationNodeNotInWorkflow: ERROR_AUTOMATION_NODE_NOT_IN_WORKFLOW,
            AutomationNodeError: ERROR_AUTOMATION_UNEXPECTED_ERROR,
        }
    )
    @validate_body(ReplaceAutomationNodeSerializer)
    def post(self, request, data: Dict, node_id: int):
        replaced_node = ReplaceAutomationNodeActionType.do(
            request.user, node_id, data["new_type"]
        )

        return Response(
            automation_node_type_registry.get_serializer(
                replaced_node, AutomationNodeSerializer
            ).data
        )


class SimulateDispatchAutomationNodeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="node_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The node to simulate the dispatch for.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_NODES_TAG],
        operation_id="simulate_dispatch_automation_node",
        description="Simulate a dispatch for a node.",
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                automation_node_type_registry, AutomationNodeSerializer
            ),
            400: get_error_schema(["ERROR_AUTOMATION_NODE_SIMULATE_DISPATCH"]),
            404: get_error_schema(["ERROR_AUTOMATION_NODE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationNodeDoesNotExist: ERROR_AUTOMATION_NODE_DOES_NOT_EXIST,
            AutomationNodeSimulateDispatchError: ERROR_AUTOMATION_NODE_SIMULATE_DISPATCH,
        }
    )
    def post(self, request, node_id: int):
        AutomationWorkflowService().toggle_test_run(
            request.user, simulate_until_node_id=node_id
        )
        return Response(status=HTTP_202_ACCEPTED)


class MoveAutomationNodeView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="node_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The node that is to be moved.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_NODES_TAG],
        operation_id="move_automation_node",
        description="Move a node in a workflow to a new position.",
        request=MoveAutomationNodeSerializer,
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                automation_node_type_registry, AutomationNodeSerializer
            ),
            400: get_error_schema(["ERROR_AUTOMATION_NODE_NOT_MOVABLE"]),
            404: get_error_schema(["ERROR_AUTOMATION_NODE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationNodeDoesNotExist: ERROR_AUTOMATION_NODE_DOES_NOT_EXIST,
            AutomationNodeNotMovable: ERROR_AUTOMATION_NODE_NOT_MOVABLE,
            AutomationNodeNotInWorkflow: ERROR_AUTOMATION_NODE_NOT_IN_WORKFLOW,
            AutomationNodeFirstNodeMustBeTrigger: ERROR_AUTOMATION_FIRST_NODE_MUST_BE_TRIGGER,
            AutomationNodeTriggerMustBeFirstNode: ERROR_AUTOMATION_TRIGGER_MUST_BE_FIRST_NODE,
            AutomationNodeReferenceNodeInvalid: ERROR_AUTOMATION_NODE_REFERENCE_NODE_INVALID,
            AutomationNodeError: ERROR_AUTOMATION_UNEXPECTED_ERROR,
        }
    )
    @validate_body(MoveAutomationNodeSerializer)
    def post(self, request, data: Dict, node_id: int):
        MoveAutomationNodeActionType.do(request.user, node_id, **data)
        return Response(status=HTTP_202_ACCEPTED)
