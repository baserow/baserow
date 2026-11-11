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
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.mcp.actions import (
    ConnectMCPOAuthClientActionType,
    DisconnectMCPOAuthClientActionType,
    UpdateMCPEndpointToolsActionType,
)
from baserow.core.mcp.exceptions import MCPEndpointDoesNotExist, MCPToolsNotAvailable
from baserow.core.mcp.groups import mcp_tool_group_registry
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.oauth.authorize import (
    deny_url,
    error_redirect_url,
    is_redirectable,
    issue_code,
    validate_query,
)
from baserow.core.mcp.oauth.throttling import MCPOAuthConsentRateThrottle
from baserow.core.mcp.oauth.tokens import endpoint_ids_with_live_refresh_token
from baserow.core.mcp.oauth.validators import LOOPBACK_HOSTS
from baserow.core.mcp.operations import CreateMCPEndpointOperationType
from baserow.core.mcp.registries import mcp_tool_registry
from baserow.core.models import WorkspaceUser
from baserow.core.registries import application_type_registry

from .errors import ERROR_MCP_ENDPOINT_DOES_NOT_EXIST, ERROR_MCP_TOOLS_NOT_AVAILABLE
from .oauth_serializers import ConsentSerializer
from .serializers import UpdateAllowedToolsSerializer


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
    is who published it. `verified` means only that: any host can publish one, so
    it is no sign the client can be trusted.
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
    verification = _verification(application)
    return {
        "client_id": application.client_id,
        # The name is empty when the client sends no client_name. A CIMD client
        # falls back to the host that published its metadata.
        "client_name": application.name
        or verification["verified_host"]
        or redirect_host,
        "redirect_host": redirect_host,
        "registration_source": application.registration_source,
        "loopback_only": _loopback_only(application),
        **verification,
    }


def _serialize_tool(tool) -> dict:
    return {
        "name": tool.name,
        "title": tool.display_title,
        "read_only": tool.read_only,
        "destructive": tool.destructive,
        "group": tool.group,
    }


def _serialize_groups(tools) -> list[dict]:
    """The groups of the given tools, in display order."""

    used = {tool.group for tool in tools}
    return [
        {
            "type": group.type,
            "title": group.title,
            "area": group.area,
            "read_only_preset": group.read_only_preset,
        }
        for group in mcp_tool_group_registry.get_ordered()
        if group.type in used
    ]


class MCPOAuthConsentView(APIView):
    permission_classes = (IsAuthenticated,)
    throttle_classes = (*APIView.throttle_classes, MCPOAuthConsentRateThrottle)

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
            str(endpoint.workspace_id): mcp_tool_registry.get_allowed_names(endpoint)
            for endpoint in MCPEndpoint.objects.filter(
                user=request.user,
                oauth_client_id=credentials["client_id"],
                workspace_id__in=[wu.workspace_id for wu in workspace_users],
            )
        }
        tools = mcp_tool_registry.get_enabled_tools()
        database_model = application_type_registry.get("database").model_class
        database_counts = dict(
            database_model.objects.filter(
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
                "tools": [_serialize_tool(tool) for tool in tools],
                "groups": _serialize_groups(tools),
            }
        )

    @map_exceptions(
        {
            WorkspaceDoesNotExist: ERROR_GROUP_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            MCPToolsNotAvailable: ERROR_MCP_TOOLS_NOT_AVAILABLE,
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
                endpoint = ConnectMCPOAuthClientActionType.do(
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


def _serialize_connection(endpoint, application, expired: bool) -> dict:
    return {
        "id": endpoint.id,
        "client_name": (application and application.name) or endpoint.name,
        **_verification(application),
        "workspace_id": endpoint.workspace_id,
        "workspace_name": endpoint.workspace.name,
        "allowed_tools": mcp_tool_registry.get_allowed_names(endpoint),
        "tool_count": len(mcp_tool_registry.get_allowed_tools(endpoint)),
        "created": endpoint.created,
        # The app has to sign in again before it can use the grant.
        "expired": expired,
    }


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
            # A grant in a workspace the user left can't be used.
            MCPEndpoint.objects.filter(
                user=request.user,
                oauth_client_id__isnull=False,
                workspace__workspaceuser__user=request.user,
            ).select_related("workspace", "user")
        )
        Application = get_application_model()
        applications = Application.objects.in_bulk(
            {endpoint.oauth_client_id for endpoint in endpoints},
            field_name="client_id",
        )
        live = endpoint_ids_with_live_refresh_token(request.user)
        tools = mcp_tool_registry.get_enabled_tools()
        return Response(
            {
                "oauth_enabled": True,
                "mcp_url": settings.MCP_RESOURCE_URL,
                "connections": [
                    _serialize_connection(
                        endpoint,
                        applications.get(endpoint.oauth_client_id),
                        expired=endpoint.id not in live,
                    )
                    for endpoint in endpoints
                ],
                "tools": [_serialize_tool(tool) for tool in tools],
                "groups": _serialize_groups(tools),
            }
        )


class MCPOAuthConnectionView(APIView):
    permission_classes = (IsAuthenticated,)

    @transaction.atomic
    @map_exceptions(
        {
            MCPEndpointDoesNotExist: ERROR_MCP_ENDPOINT_DOES_NOT_EXIST,
            MCPToolsNotAvailable: ERROR_MCP_TOOLS_NOT_AVAILABLE,
        }
    )
    @validate_body(UpdateAllowedToolsSerializer)
    def patch(self, request, data, connection_id):
        """
        Changes the tools an OAuth client may use. The client keeps its tokens and
        gets the new tools on its next request.
        """

        _require_oauth_enabled()
        endpoint = MCPEndpointHandler().get_oauth_grant(
            request.user,
            connection_id,
            base_queryset=MCPEndpoint.objects.select_for_update(of=("self",)),
        )
        endpoint = UpdateMCPEndpointToolsActionType.do(
            request.user, endpoint, data["allowed_tools"]
        )
        Application = get_application_model()
        application = Application.objects.filter(
            client_id=endpoint.oauth_client_id
        ).first()
        live = endpoint_ids_with_live_refresh_token(request.user)
        return Response(
            _serialize_connection(
                endpoint,
                application,
                expired=endpoint.id not in live,
            )
        )

    @transaction.atomic
    @map_exceptions(
        {
            MCPEndpointDoesNotExist: ERROR_MCP_ENDPOINT_DOES_NOT_EXIST,
        }
    )
    def delete(self, request, connection_id):
        """
        Disconnects an OAuth client by deleting its grant endpoint, which revokes
        its tokens. Only needs the grant to be the user's, like listing it.
        """

        _require_oauth_enabled()
        endpoint = MCPEndpointHandler().get_oauth_grant(request.user, connection_id)
        DisconnectMCPOAuthClientActionType.do(request.user, endpoint)
        return Response(status=status.HTTP_204_NO_CONTENT)
