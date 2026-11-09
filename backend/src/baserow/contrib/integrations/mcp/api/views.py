from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.integrations.errors import ERROR_INTEGRATION_DOES_NOT_EXIST
from baserow.api.integrations.serializers import IntegrationSerializer
from baserow.api.schemas import get_error_schema
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.registries import integration_type_registry

from ..exceptions import MCPServerUnreachable
from ..service import MCPServerService

ERROR_MCP_SERVER_UNREACHABLE = (
    "ERROR_MCP_SERVER_UNREACHABLE",
    400,
    "The MCP server could not be reached or failed to list its tools.",
)

INTEGRATION_ID_PARAMETER = OpenApiParameter(
    name="integration_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the MCP server integration.",
)

EXCEPTIONS = {
    IntegrationDoesNotExist: ERROR_INTEGRATION_DOES_NOT_EXIST,
    MCPServerUnreachable: ERROR_MCP_SERVER_UNREACHABLE,
}


class MCPToolSettingsSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    enabled = serializers.BooleanField(required=False)
    changes_data = serializers.BooleanField(required=False)


class MCPToolsUpdateSerializer(serializers.Serializer):
    tools = MCPToolSettingsSerializer(many=True)


def _respond(integration) -> Response:
    return Response(
        integration_type_registry.get_serializer(
            integration, IntegrationSerializer
        ).data
    )


class MCPServerRefreshToolsView(APIView):
    @extend_schema(
        parameters=[INTEGRATION_ID_PARAMETER],
        tags=["Integrations"],
        operation_id="refresh_mcp_server_tools",
        description=(
            "Lists the MCP server's tools and stores them. New tools start off. A "
            "tool that is on and changed is turned off until it is reviewed."
        ),
        request=None,
        responses={
            200: IntegrationSerializer,
            400: get_error_schema(["ERROR_MCP_SERVER_UNREACHABLE"]),
            404: get_error_schema(["ERROR_INTEGRATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(EXCEPTIONS)
    def post(self, request, integration_id: int):
        # No transaction around the view: the server may take a while to answer.
        return _respond(MCPServerService().refresh_tools(request.user, integration_id))


class MCPServerToolsView(APIView):
    @extend_schema(
        parameters=[INTEGRATION_ID_PARAMETER],
        tags=["Integrations"],
        operation_id="update_mcp_server_tools",
        description=(
            "Turns the given tools on or off and sets whether they change data. "
            "Saving a tool marks its current definition as reviewed."
        ),
        request=MCPToolsUpdateSerializer,
        responses={
            200: IntegrationSerializer,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
            404: get_error_schema(["ERROR_INTEGRATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(EXCEPTIONS)
    @validate_body(MCPToolsUpdateSerializer, return_validated=True)
    def patch(self, request, integration_id: int, data: dict):
        return _respond(
            MCPServerService().update_tools(request.user, integration_id, data["tools"])
        )
