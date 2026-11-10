from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.integrations.errors import ERROR_INTEGRATION_DOES_NOT_EXIST
from baserow.api.integrations.serializers import IntegrationSerializer
from baserow.api.schemas import get_error_schema
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.registries import integration_type_registry

from .. import oauth
from ..exceptions import (
    MCPOAuthFailed,
    MCPOAuthStateInvalid,
    MCPServerNotConnected,
    MCPServerRefusedCredential,
    MCPServerUnreachable,
)
from ..service import MCPServerService
from .errors import (
    ERROR_MCP_OAUTH_FAILED,
    ERROR_MCP_OAUTH_STATE_INVALID,
    ERROR_MCP_SERVER_NOT_CONNECTED,
    ERROR_MCP_SERVER_REFUSED_CREDENTIAL,
    ERROR_MCP_SERVER_UNREACHABLE,
)
from .serializers import (
    MCPServerOAuthCompleteSerializer,
    MCPServerOAuthStartSerializer,
    MCPToolsUpdateSerializer,
)

INTEGRATION_ID_PARAMETER = OpenApiParameter(
    name="integration_id",
    location=OpenApiParameter.PATH,
    type=OpenApiTypes.INT,
    description="The id of the MCP server integration.",
)

EXCEPTIONS = {
    IntegrationDoesNotExist: ERROR_INTEGRATION_DOES_NOT_EXIST,
    MCPServerRefusedCredential: ERROR_MCP_SERVER_REFUSED_CREDENTIAL,
    MCPServerUnreachable: ERROR_MCP_SERVER_UNREACHABLE,
    MCPServerNotConnected: ERROR_MCP_SERVER_NOT_CONNECTED,
    MCPOAuthFailed: ERROR_MCP_OAUTH_FAILED,
    MCPOAuthStateInvalid: ERROR_MCP_OAUTH_STATE_INVALID,
}


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
            400: get_error_schema(
                [
                    "ERROR_MCP_SERVER_UNREACHABLE",
                    "ERROR_MCP_SERVER_REFUSED_CREDENTIAL",
                    "ERROR_MCP_SERVER_NOT_CONNECTED",
                ]
            ),
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


class MCPServerOAuthStartView(APIView):
    @extend_schema(
        parameters=[INTEGRATION_ID_PARAMETER],
        tags=["Integrations"],
        operation_id="start_mcp_server_oauth",
        description=(
            "Starts connecting an account to an MCP server that uses OAuth. Open "
            "the returned URL in a popup: the provider redirects back to a Baserow "
            "page, which finishes the sign-in with the complete endpoint."
        ),
        request=None,
        responses={
            200: MCPServerOAuthStartSerializer,
            400: get_error_schema(["ERROR_MCP_OAUTH_FAILED"]),
            404: get_error_schema(["ERROR_INTEGRATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(EXCEPTIONS)
    def post(self, request, integration_id: int):
        url = MCPServerService().start_oauth(request.user, integration_id)
        return Response({"authorization_url": url})


class MCPServerOAuthDisconnectView(APIView):
    @extend_schema(
        parameters=[INTEGRATION_ID_PARAMETER],
        tags=["Integrations"],
        operation_id="disconnect_mcp_server_oauth",
        description="Forgets the account connected to an MCP server.",
        request=None,
        responses={
            200: IntegrationSerializer,
            404: get_error_schema(["ERROR_INTEGRATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(EXCEPTIONS)
    def post(self, request, integration_id: int):
        return _respond(
            MCPServerService().disconnect_oauth(request.user, integration_id)
        )


class MCPServerOAuthCompleteView(APIView):
    @extend_schema(
        tags=["Integrations"],
        operation_id="complete_mcp_server_oauth",
        description=(
            "Finishes connecting an account to an MCP server with the code the "
            "provider redirected back with. Only the user who started the "
            "sign-in can finish it."
        ),
        request=MCPServerOAuthCompleteSerializer,
        responses={
            200: IntegrationSerializer,
            400: get_error_schema(
                ["ERROR_MCP_OAUTH_FAILED", "ERROR_MCP_OAUTH_STATE_INVALID"]
            ),
            404: get_error_schema(["ERROR_INTEGRATION_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(EXCEPTIONS)
    @validate_body(MCPServerOAuthCompleteSerializer)
    def post(self, request, data: dict):
        return _respond(
            MCPServerService().complete_oauth(request.user, data["state"], data["code"])
        )


class MCPClientMetadataView(APIView):
    authentication_classes = []
    permission_classes = (AllowAny,)

    @extend_schema(exclude=True)
    def get(self, request):
        return Response(oauth.get_client_metadata())
