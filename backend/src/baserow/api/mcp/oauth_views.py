from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.http import Http404

from oauth2_provider.exceptions import OAuthToolkitError
from oauth2_provider.models import get_application_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.contrib.database.models import Database
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.mcp.exceptions import MCPEndpointDoesNotExist
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.oauth.authorize import (
    deny_url,
    error_redirect_url,
    is_redirectable,
    issue_code,
    validate_query,
)
from baserow.core.mcp.oauth.validators import LOOPBACK_HOSTS
from baserow.core.mcp.operations import CreateMCPEndpointOperationType
from baserow.core.mcp.registries import mcp_tool_registry
from baserow.core.models import WorkspaceUser

from .errors import ERROR_MCP_ENDPOINT_DOES_NOT_EXIST
from .oauth_serializers import ConsentSerializer


def _require_oauth_enabled():
    if not settings.BASEROW_MCP_OAUTH_ENABLED:
        raise Http404()


def _loopback_only(application) -> bool:
    """
    True when every redirect URI is a loopback address. Any local program can
    receive those, so the consent page warns before trusting the client's name.
    """

    hosts = {urlparse(uri).hostname for uri in application.redirect_uris.split()}
    return bool(hosts) and hosts <= LOOPBACK_HOSTS


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
    A CIMD client's metadata is served from its client_id URL, so the URL's host
    is who published it.
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
    redirect_host = urlparse(credentials["redirect_uri"]).hostname
    return {
        "client_id": application.client_id,
        # DCR stores an empty name when the client sends no client_name.
        "client_name": application.name or redirect_host,
        "redirect_host": redirect_host,
        "registration_source": application.registration_source,
        "loopback_only": _loopback_only(application),
        **_verification(application),
    }


class MCPOAuthConsentView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        _require_oauth_enabled()
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
        handler = CoreHandler()
        workspace_users = [
            wu
            for wu in workspace_users
            if handler.check_permissions(
                request.user,
                CreateMCPEndpointOperationType.type,
                workspace=wu.workspace,
                context=wu.workspace,
                raise_permission_exceptions=False,
            )
        ]
        grants = {
            str(endpoint.workspace_id): endpoint.allowed_tools
            for endpoint in MCPEndpoint.objects.filter(
                user=request.user,
                oauth_client_id=credentials["client_id"],
                workspace_id__in=[wu.workspace_id for wu in workspace_users],
            )
        }
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
                "grants": grants,
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

    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @validate_body(ConsentSerializer)
    def post(self, request, data):
        _require_oauth_enabled()
        # Validated outside the transaction, because validation may fetch the
        # client's metadata document over HTTP. The library re-checks the client
        # when it issues the code, which only refetches a stale document.
        try:
            authorize_request, credentials = validate_query(
                request, request.user, data["query"]
            )
        except OAuthToolkitError as error:
            return _invalid_request(error)

        if not data["allow"]:
            return Response({"redirect_url": deny_url(authorize_request, credentials)})

        workspace = CoreHandler().get_workspace(data["workspace_id"])
        client = _client_info(credentials)
        try:
            # The grant only persists if a code was issued for it.
            with transaction.atomic():
                endpoint = MCPEndpointHandler().grant_oauth_client(
                    request.user,
                    workspace,
                    client["client_id"],
                    client["client_name"][
                        : MCPEndpoint._meta.get_field("name").max_length
                    ],
                    data["tools"],
                )
                redirect_url = issue_code(authorize_request, credentials, endpoint)
        except OAuthToolkitError as error:
            if is_redirectable(error):
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
            # A grant in a workspace the user left can't be used or deleted.
            MCPEndpoint.objects.filter(
                user=request.user,
                oauth_client_id__isnull=False,
                workspace__workspaceuser__user=request.user,
            ).select_related("workspace")
        )
        Application = get_application_model()
        applications = Application.objects.in_bulk(
            {endpoint.oauth_client_id for endpoint in endpoints},
            field_name="client_id",
        )
        connections = []
        for endpoint in endpoints:
            application = applications.get(endpoint.oauth_client_id)
            connections.append(
                {
                    "id": endpoint.id,
                    "client_name": (application and application.name) or endpoint.name,
                    **_verification(application),
                    "workspace_id": endpoint.workspace_id,
                    "workspace_name": endpoint.workspace.name,
                    "allowed_tools": endpoint.allowed_tools,
                    "tool_count": len(mcp_tool_registry.get_allowed_tools(endpoint)),
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

        _require_oauth_enabled()
        endpoint = MCPEndpointHandler().get_endpoint(
            request.user,
            connection_id,
            base_queryset=MCPEndpoint.objects.filter(oauth_client_id__isnull=False),
        )
        MCPEndpointHandler().delete_endpoint(request.user, endpoint)
        return Response(status=status.HTTP_204_NO_CONTENT)
