from typing import Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    validate_body_custom_fields,
)
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.utils import (
    DiscriminatorCustomFieldsMappingSerializer,
)
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.automation.api.nodes.serializers import (
    AutomationNodeSerializer,
    CreateAutomationNodeSerializer,
)
from baserow.contrib.automation.api.workflows.errors import (
    ERROR_AUTOMATION_WORKFLOW_DOES_NOT_EXIST
)
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowDoesNotExist
)
from baserow.contrib.automation.workflows.handler import AutomationWorkflowHandler
from baserow.contrib.automation.nodes.service import AutomationNodeService


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
        tags=["Automation nodes"],
        operation_id="create_automation_workflow_node",
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
        }
    )
    @validate_body_custom_fields(
        automation_node_type_registry,
        base_serializer_class=CreateAutomationNodeSerializer,
    )
    def post(self, request, data: Dict, workflow_id: int):
        type_name = data.pop("type")
        node_type = automation_node_type_registry.get(type_name)
        workflow = AutomationWorkflowHandler().get_workflow(workflow_id)

        node = AutomationNodeService().create_node(
            request.user, node_type, workflow, **data
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
        tags=["Automation nodes"],
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
        workflow = AutomationWorkflowHandler().get_workflow(workflow_id)

        nodes = AutomationNodeService().get_nodes(request.user, workflow)
        
        data = [
            automation_node_type_registry.get_serializer(
                node, AutomationNodeSerializer
            ).data
            for node in nodes
        ]

        return Response(data)
