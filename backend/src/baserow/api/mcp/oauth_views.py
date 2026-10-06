from urllib.parse import urlparse

from django.db import transaction

from oauth2_provider.exceptions import OAuthToolkitError
from oauth2_provider.models import get_application_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.errors import ERROR_GROUP_DOES_NOT_EXIST, ERROR_USER_NOT_IN_GROUP
from baserow.core.exceptions import UserNotInWorkspace, WorkspaceDoesNotExist
from baserow.core.handler import CoreHandler
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.oauth.authorize import (
    error_redirect_url,
    issue_code,
    validate_query,
)
from baserow.core.mcp.registries import mcp_tool_registry
from baserow.core.models import WorkspaceUser

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


def _client_info(credentials: dict) -> dict:
    application = get_application_model().objects.get(
        client_id=credentials["client_id"]
    )
    return {
        "client_id": application.client_id,
        "client_name": application.name,
        "redirect_host": urlparse(credentials["redirect_uri"]).hostname,
        "registration_source": application.registration_source,
    }


class MCPOAuthConsentView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        query = request.query_params.get("query", "")
        try:
            _, credentials = validate_query(request, request.user, query)
        except OAuthToolkitError as error:
            return _invalid_request(error)

        workspace_users = (
            WorkspaceUser.objects.filter(user=request.user)
            .select_related("workspace")
            .order_by("order", "id")
        )
        return Response(
            {
                **_client_info(credentials),
                "workspaces": [
                    {"id": wu.workspace_id, "name": wu.workspace.name}
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
