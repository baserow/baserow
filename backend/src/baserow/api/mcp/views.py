from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import get_error_schema
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.mcp.actions import (
    CreateMCPEndpointActionType,
    DeleteMCPEndpointActionType,
    UpdateMCPEndpointActionType,
)
from baserow.core.mcp.exceptions import (
    MaximumUniqueEndpointTriesError,
    MCPEndpointDoesNotBelongToUser,
    MCPEndpointDoesNotExist,
)
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.models import MCPEndpoint

from .errors import (
    ERROR_MAXIMUM_UNIQUE_ENDPOINT_TRIES,
    ERROR_MCP_ENDPOINT_DOES_NOT_BELONG_TO_USER,
    ERROR_MCP_ENDPOINT_DOES_NOT_EXIST,
)
from .serializers import (
    CreateMCPEndpointSerializer,
    MCPEndpointSerializer,
    UpdateMCPEndpointSerializer,
)


class MCPEndpointsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["MCP endpoints"],
        operation_id="list_mcp_endpoints",
        description=(
            "Lists all the MCP (Model Context Protocol) endpoints of a user. These can"
            "be used to directly integrate with an LLM like Claude, and let the LLM "
            "perform actions directly in Baserow. Treat your MCP URL like a password,"
            "as it has the ability to modify data in Baserow."
        ),
        responses={200: MCPEndpointSerializer(many=True)},
    )
    def get(self, request):
        """Lists all the MCP endpoints of the authenticated user."""

        endpoints = MCPEndpoint.objects.filter(user=request.user).select_related(
            "workspace"
        )
        serializer = MCPEndpointSerializer(endpoints, many=True)
        return Response(serializer.data)

    @extend_schema(
        tags=["MCP endpoints"],
        operation_id="create_mcp_endpoint",
        description=(
            "Creates a new MCP endpoint for a given workspace. The endpoint can be "
            "used for an MCP integration."
        ),
        request=CreateMCPEndpointSerializer,
        responses={
            200: MCPEndpointSerializer,
            400: get_error_schema(
                ["ERROR_USER_NOT_IN_GROUP", "ERROR_MAXIMUM_UNIQUE_ENDPOINT_TRIES"]
            ),
        },
    )
    @validate_body(CreateMCPEndpointSerializer)
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            MaximumUniqueEndpointTriesError: ERROR_MAXIMUM_UNIQUE_ENDPOINT_TRIES,
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def post(self, request, data):
        """Creates a new MCP endpoint for the authenticated user."""

        workspace = CoreHandler().get_workspace(data["workspace_id"])
        endpoint = action_type_registry.get(CreateMCPEndpointActionType.type).do(
            request.user, workspace, data["name"]
        )
        serializer = MCPEndpointSerializer(endpoint)
        return Response(serializer.data)


class MCPEndpointView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["MCP endpoints"],
        operation_id="get_mcp_endpoint",
        description="Returns the requested MCP endpoint if the authorized user has access to it.",
        responses={
            200: MCPEndpointSerializer,
            404: get_error_schema(["ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({MCPEndpointDoesNotExist: ERROR_MCP_ENDPOINT_DOES_NOT_EXIST})
    def get(self, request, endpoint_id):
        """Returns the requested MCP endpoint if the user has access to it."""

        endpoint = MCPEndpointHandler().get_endpoint(request.user, endpoint_id)
        serializer = MCPEndpointSerializer(endpoint)
        return Response(serializer.data)

    @extend_schema(
        tags=["MCP endpoints"],
        operation_id="update_mcp_endpoint",
        description="Updates the MCP endpoint if the authorized user has access to it.",
        request=UpdateMCPEndpointSerializer,
        responses={
            200: MCPEndpointSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_MCP_ENDPOINT_DOES_NOT_BELONG_TO_USER",
                ]
            ),
            404: get_error_schema(["ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"]),
        },
    )
    @validate_body(UpdateMCPEndpointSerializer)
    @map_exceptions(
        {
            MCPEndpointDoesNotExist: ERROR_MCP_ENDPOINT_DOES_NOT_EXIST,
            MCPEndpointDoesNotBelongToUser: ERROR_MCP_ENDPOINT_DOES_NOT_BELONG_TO_USER,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @transaction.atomic
    def patch(self, request, data, endpoint_id):
        """Updates the MCP endpoint if the user has access to it."""

        endpoint = MCPEndpointHandler().get_endpoint(
            request.user,
            endpoint_id,
            base_queryset=MCPEndpoint.objects.select_for_update(of=("self",)),
        )

        endpoint = action_type_registry.get(UpdateMCPEndpointActionType.type).do(
            request.user, endpoint, data["name"]
        )
        serializer = MCPEndpointSerializer(endpoint)
        return Response(serializer.data)

    @extend_schema(
        tags=["MCP endpoints"],
        operation_id="delete_mcp_endpoint",
        description="Deletes an MCP endpoint if the authorized user has access to it.",
        responses={
            204: None,
            400: get_error_schema(["ERROR_MCP_ENDPOINT_DOES_NOT_BELONG_TO_USER"]),
            404: get_error_schema(["ERROR_MCP_ENDPOINT_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            MCPEndpointDoesNotExist: ERROR_MCP_ENDPOINT_DOES_NOT_EXIST,
            MCPEndpointDoesNotBelongToUser: ERROR_MCP_ENDPOINT_DOES_NOT_BELONG_TO_USER,
        }
    )
    @transaction.atomic
    def delete(self, request, endpoint_id):
        """Deletes an MCP endpoint if the user has access to it."""

        endpoint = MCPEndpointHandler().get_endpoint(request.user, endpoint_id)

        action_type_registry.get(DeleteMCPEndpointActionType.type).do(
            request.user, endpoint
        )
        return Response(status=204)
