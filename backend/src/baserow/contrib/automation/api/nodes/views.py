from typing import Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body,
    validate_body_custom_fields,
)
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.utils import DiscriminatorCustomFieldsMappingSerializer
from baserow.contrib.automation.api.nodes.errors import (
    ERROR_AUTOMATION_NODE_BEFORE_INVALID,
    ERROR_AUTOMATION_NODE_DOES_NOT_EXIST,
    ERROR_AUTOMATION_NODE_NOT_IN_WORKFLOW,
    ERROR_AUTOMATION_NODE_NOT_REPLACEABLE,
    ERROR_AUTOMATION_TRIGGER_NODE_MODIFICATION_DISALLOWED,
)
from baserow.contrib.automation.api.nodes.serializers import (
    AutomationNodeSerializer,
    CreateAutomationNodeSerializer,
    OrderAutomationNodesSerializer,
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
    OrderAutomationNodesActionType,
    ReplaceAutomationNodeActionType,
    UpdateAutomationNodeActionType,
)
from baserow.contrib.automation.nodes.exceptions import (
    AutomationNodeBeforeInvalid,
    AutomationNodeDoesNotExist,
    AutomationNodeNotInWorkflow,
    AutomationNodeTypeNotReplaceable,
    AutomationTriggerModificationDisallowed,
)
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
            AutomationNodeBeforeInvalid: ERROR_AUTOMATION_NODE_BEFORE_INVALID,
            AutomationNodeDoesNotExist: ERROR_AUTOMATION_NODE_DOES_NOT_EXIST,
            AutomationTriggerModificationDisallowed: ERROR_AUTOMATION_TRIGGER_NODE_MODIFICATION_DISALLOWED,
        }
    )
    @validate_body_custom_fields(
        automation_node_type_registry,
        base_serializer_class=CreateAutomationNodeSerializer,
    )
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
        }
    )
    @validate_body_custom_fields(
        automation_node_type_registry,
        base_serializer_class=UpdateAutomationNodeSerializer,
        partial=True,
    )
    def patch(self, request, data: Dict, node_id: int):
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
            AutomationTriggerModificationDisallowed: ERROR_AUTOMATION_TRIGGER_NODE_MODIFICATION_DISALLOWED,
        }
    )
    @transaction.atomic
    def delete(self, request, node_id: int):
        DeleteAutomationNodeActionType.do(request.user, node_id)

        return Response(status=204)


class OrderAutomationNodesView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="workflow_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The workflow that the nodes belong to.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=[AUTOMATION_NODES_TAG],
        operation_id="order_automation_nodes",
        description="Apply a new order to the nodes of a workflow.",
        request=OrderAutomationNodesSerializer,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_AUTOMATION_NODE_NOT_IN_WORKFLOW",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_AUTOMATION_NODE_DOES_NOT_EXIST",
                    "ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            AutomationWorkflowDoesNotExist: ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST,
            AutomationNodeDoesNotExist: ERROR_AUTOMATION_NODE_DOES_NOT_EXIST,
            AutomationNodeNotInWorkflow: ERROR_AUTOMATION_NODE_NOT_IN_WORKFLOW,
        }
    )
    @validate_body(OrderAutomationNodesSerializer)
    def post(self, request, data: Dict, workflow_id: int):
        OrderAutomationNodesActionType.do(request.user, workflow_id, data["node_ids"])

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
        request=OrderAutomationNodesSerializer,
        responses={
            204: None,
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
            AutomationTriggerModificationDisallowed: ERROR_AUTOMATION_TRIGGER_NODE_MODIFICATION_DISALLOWED,
        }
    )
    def post(self, request, node_id):
        """Duplicate an automation node."""

        DuplicateAutomationNodeActionType.do(request.user, node_id)

        return Response(status=204)


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
            AutomationNodeTypeNotReplaceable: ERROR_AUTOMATION_NODE_NOT_REPLACEABLE,
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
