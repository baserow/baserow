from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.db.models import Count

from oauth2_provider.exceptions import OAuthToolkitError
from oauth2_provider.models import get_application_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.contrib.database.models import Database
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.mcp.exceptions import MCPEndpointDoesNotExist
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.oauth.authorize import (
    error_redirect_url,
    issue_code,
    validate_query,
)
from baserow.core.mcp.registries import mcp_tool_registry
from baserow.core.models import WorkspaceUser

from .errors import ERROR_MCP_ENDPOINT_DOES_NOT_EXIST
from .oauth_serializers import ConsentSerializer


def _invalid_request(error: OAuthToolkitError) -> Response:
    oauthlib_error = error.oauthlib_error
    return Response(
        {
            "error": oauthlib_error.error,
            "detail": oauthlib_error.description,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


def _verification(application) -> dict:
    """
    A CIMD client_id is an https URL on an allowlisted host, so the host is
    vouched for by the allowlist.
    """

    Application = get_application_model()
    verified = (
        application is not None
        and application.registration_source == Application.RegistrationSource.CIMD
    )
    return {
        "verified": verified,
        "verified_host": urlparse(application.client_id).hostname if verified else None,
    }


def _client_info(credentials: dict) -> dict:
    Application = get_application_model()
    application = Application.objects.get(client_id=credentials["client_id"])
    return {
        "client_id": application.client_id,
        "client_name": application.name,
        "redirect_host": urlparse(credentials["redirect_uri"]).hostname,
        "registration_source": application.registration_source,
        **_verification(application),
    }


class MCPOAuthConsentView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        query = request.query_params.get("query", "")
        try:
            _, credentials = validate_query(request, request.user, query)
        except OAuthToolkitError as error:
            return _invalid_request(error)

        workspace_users = list(
            WorkspaceUser.objects.filter(user=request.user)
            .select_related("workspace")
            .order_by("order", "id")
        )
        database_counts = dict(
            Database.objects.filter(
                workspace_id__in=[wu.workspace_id for wu in workspace_users]
            )
            .values_list("workspace_id")
            .annotate(count=Count("id"))
            .order_by()
        )
        return Response(
            {
                **_client_info(credentials),
                "workspaces": [
                    {
                        "id": wu.workspace_id,
                        "name": wu.workspace.name,
                        "database_count": database_counts.get(wu.workspace_id, 0),
                    }
                    for wu in workspace_users
                ],
                "tools": [
                    {
                        "name": tool.name,
                        "title": tool.display_title,
                        "read_only": tool.read_only,
                        "destructive": tool.destructive,
                    }
                    for tool in mcp_tool_registry.get_enabled_tools()
                ],
            }
        )

    @transaction.atomic
    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def post(self, request):
        serializer = ConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Validate before creating anything, so a bad request leaves no endpoint.
        try:
            _, credentials = validate_query(request, request.user, data["query"])
        except OAuthToolkitError as error:
            return _invalid_request(error)

        endpoint = None
        if data["allow"]:
            workspace = CoreHandler().get_workspace(data["workspace_id"])
            client = _client_info(credentials)
            endpoint = MCPEndpointHandler().grant_oauth_client(
                request.user,
                workspace,
                client["client_id"],
                client["client_name"][: MCPEndpoint._meta.get_field("name").max_length],
                data["tools"],
            )

        try:
            redirect_url = issue_code(
                request, request.user, data["query"], endpoint, data["allow"]
            )
        except OAuthToolkitError as error:
            if error.oauthlib_error.redirect_uri:
                return Response({"redirect_url": error_redirect_url(request, error)})
            return _invalid_request(error)
        return Response({"redirect_url": redirect_url})


class MCPOAuthConnectionsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        """
        Lists the OAuth clients the user granted access to, one per grant
        endpoint, with the URL MCP clients connect to.
        """

        if not settings.BASEROW_MCP_OAUTH_ENABLED:
            return Response(
                {"oauth_enabled": False, "mcp_url": None, "connections": []}
            )

        endpoints = list(
            MCPEndpoint.objects.filter(
                user=request.user, oauth_client_id__isnull=False
            ).select_related("workspace")
        )
        Application = get_application_model()
        applications = Application.objects.in_bulk(
            {endpoint.oauth_client_id for endpoint in endpoints},
            field_name="client_id",
        )
        enabled_tool_count = len(mcp_tool_registry.get_enabled_tools())
        connections = []
        for endpoint in endpoints:
            application = applications.get(endpoint.oauth_client_id)
            allowed_tools = endpoint.allowed_tools
            connections.append(
                {
                    "id": endpoint.id,
                    "client_name": application.name if application else endpoint.name,
                    **_verification(application),
                    "workspace_id": endpoint.workspace_id,
                    "workspace_name": endpoint.workspace.name,
                    "allowed_tools": allowed_tools,
                    "tool_count": (
                        enabled_tool_count
                        if allowed_tools is None
                        else len(allowed_tools)
                    ),
                    "created": endpoint.created,
                }
            )
        return Response(
            {
                "oauth_enabled": True,
                "mcp_url": settings.MCP_RESOURCE_URL,
                "connections": connections,
            }
        )


class MCPOAuthConnectionView(APIView):
    permission_classes = (IsAuthenticated,)

    @transaction.atomic
    @map_exceptions(
        {
            MCPEndpointDoesNotExist: ERROR_MCP_ENDPOINT_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def delete(self, request, connection_id):
        """
        Disconnects an OAuth client by deleting its grant endpoint, which revokes
        its tokens.
        """

        endpoint = MCPEndpointHandler().get_endpoint(
            request.user,
            connection_id,
            base_queryset=MCPEndpoint.objects.filter(oauth_client_id__isnull=False),
        )
        MCPEndpointHandler().delete_endpoint(request.user, endpoint)
        return Response(status=status.HTTP_204_NO_CONTENT)
