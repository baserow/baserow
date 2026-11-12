from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.core.handler import CoreHandler
from baserow.core.utils import random_string

from ..models import Workspace, WorkspaceUser
from .constants import LEGACY_DEFAULT_TOOLS
from .exceptions import (
    MaximumUniqueEndpointTriesError,
    MCPEndpointDoesNotBelongToUser,
    MCPEndpointDoesNotExist,
    MCPToolsNotAvailable,
)
from .models import MCPEndpoint
from .operations import (
    CreateMCPEndpointOperationType,
    DeleteMCPEndpointOperationType,
    ReadMCPEndpointOperationType,
    UpdateMCPEndpointOperationType,
)
from .registries import mcp_tool_registry


class MCPEndpointHandler:
    def get_endpoint(
        self, user: AbstractUser, endpoint_id: int, base_queryset: QuerySet = None
    ) -> MCPEndpoint:
        """
        Fetches a single key MCP endpoint and checks if the user belongs to the
        workspace. OAuth grants are never returned, use `get_oauth_grant` for those.

        :param user: The user on whose behalf the endpoint is requested.
        :type user: User
        :param endpoint_id: The id of the requested endpoint.
        :type endpoint_id: int
        :param base_queryset: The base queryset from where to select the endpoint
            object from. This can for example be used to do a `select_related`.
        :type base_queryset: Queryset
        :raises MCPEndpointDoesNotExist: Raised when the requested endpoint was not
            found or if it does not belong to the user.
        :return: The fetched endpoint.
        :rtype: MCPEndpoint
        """

        if base_queryset is None:
            base_queryset = MCPEndpoint.objects

        try:
            endpoint = base_queryset.select_related("workspace").get(
                id=endpoint_id, user=user, oauth_client_id__isnull=True
            )
        except MCPEndpoint.DoesNotExist:
            raise MCPEndpointDoesNotExist(
                f"The MCP endpoint with id {endpoint_id} does not exist."
            )

        workspace = endpoint.workspace
        CoreHandler().check_permissions(
            user,
            ReadMCPEndpointOperationType.type,
            workspace=workspace,
            context=endpoint.workspace,
        )

        return endpoint

    def generate_unique_key(self, length: int = 32, max_tries: int = 1000) -> str:
        """
        Generates a unique MCP endpoint key.

        :param length: Indicates the amount of characters that the endpoint key must
            contain.
        :param max_tries: The maximum amount of tries to check if an endpoint with the
            key already exists.
        :raises MaximumUniqueEndpointTriesError: When the maximum amount of tries has
            been exceeded. A new generated endpoint key is tried every time the key
            already exists.
        :return: A unique endpoint key
        """

        i = 0

        while True:
            if i > max_tries:
                raise MaximumUniqueEndpointTriesError(
                    f"Tried {max_tries} endpoint keys, but none of them are unique."
                )

            i += 1
            key = random_string(length)

            if not MCPEndpoint.objects.filter(key=key).exists():
                return key

    def get_default_tools(self) -> list[str]:
        """
        The tools a new endpoint key starts with: every read-only tool that isn't
        off by default, plus the tools endpoint keys always had. The user can change
        them afterwards.
        """

        return [
            tool.name
            for tool in mcp_tool_registry.get_enabled_tools()
            if (tool.read_only and not tool.off_by_default)
            or tool.name in LEGACY_DEFAULT_TOOLS
        ]

    def create_endpoint(
        self,
        user: AbstractUser,
        workspace: Workspace,
        name: str,
    ) -> MCPEndpoint:
        """
        Creates a new MCP endpoint.

        :param user: The user of whose behalf the endpoint is created.
        :type user: User
        :param workspace: The workspace object of which the endpoint is related to.
        :type workspace: Workspace
        :param name: The name of the endpoint.
        :type name: str
        :return: The created endpoint instance.
        :rtype: MCPEndpoint
        """

        CoreHandler().check_permissions(
            user,
            CreateMCPEndpointOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        endpoint = MCPEndpoint.objects.create(
            name=name,
            key=self.generate_unique_key(),
            user=user,
            workspace=workspace,
            allowed_tools=self.get_default_tools(),
        )

        return endpoint

    def grant_oauth_client(
        self,
        user: AbstractUser,
        workspace: Workspace,
        client_id: str,
        name: str,
        allowed_tools: list[str],
    ) -> tuple[MCPEndpoint, bool]:
        """
        Returns the grant backing an OAuth client's access to a workspace, creating
        it on first consent and replacing its name and allowed tools afterwards.

        :param user: The user giving consent.
        :param workspace: The workspace the client gets access to.
        :param client_id: The OAuth client id.
        :param name: The client name, stored as the grant name.
        :param allowed_tools: The tool names the client may use.
        :raises MCPToolsNotAvailable: When a name isn't an enabled tool.
        :return: The created or updated grant, and whether it was created.
        """

        # Removing the member deletes this row and then the member's grants. With
        # the row locked, a removal running at the same time either waits and then
        # deletes this grant too, or commits first and the check below fails.
        WorkspaceUser.objects.select_for_update().filter(
            user=user, workspace=workspace
        ).first()
        CoreHandler().check_permissions(
            user,
            CreateMCPEndpointOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        allowed_tools = self._check_tools(allowed_tools)
        # get_or_create retries the lookup when a parallel consent created the row
        # first, so the unique constraint never surfaces as an error.
        endpoint, created = MCPEndpoint.objects.get_or_create(
            user=user,
            workspace=workspace,
            oauth_client_id=client_id,
            defaults={"name": name, "allowed_tools": allowed_tools, "key": None},
        )
        if not created:
            CoreHandler().check_permissions(
                user,
                UpdateMCPEndpointOperationType.type,
                workspace=workspace,
                context=endpoint.workspace,
            )
            # The client may have been renamed since the first consent.
            endpoint.name = name
            endpoint.allowed_tools = allowed_tools
            endpoint.save(update_fields=["name", "allowed_tools"])
        return endpoint, created

    def update_endpoint(
        self, user: AbstractUser, endpoint: MCPEndpoint, name: str
    ) -> MCPEndpoint:
        """
        Updates an existing MCP endpoint.

        :param user: The user on whose behalf the endpoint is updated.
        :param endpoint: The endpoint object that needs to be updated.
        :param name: The new name of the endpoint.
        :raises MCPEndpointDoesNotBelongToUser: When the provided endpoint does not
            belong the provided user.
        :return: The updated endpoint instance.
        :rtype: MCPEndpoint
        """

        if not user.id == endpoint.user_id:
            raise MCPEndpointDoesNotBelongToUser(
                "The user is not authorized to update the endpoint."
            )

        CoreHandler().check_permissions(
            user,
            UpdateMCPEndpointOperationType.type,
            workspace=endpoint.workspace,
            context=endpoint.workspace,
        )

        endpoint.name = name
        endpoint.save()

        return endpoint

    def update_allowed_tools(
        self, user: AbstractUser, endpoint: MCPEndpoint, names: list[str]
    ) -> MCPEndpoint:
        """
        Replaces the tools an endpoint key or OAuth grant may use. Takes effect on
        the next MCP request, so a connected app doesn't need to sign in again.

        Removing tools needs no permission, like disconnecting an app. Stored names
        of tools that are currently disabled are kept, because the user can't see
        them to choose.

        :param user: The user on whose behalf the tools are changed.
        :param endpoint: The endpoint or grant to change.
        :param names: The tool names the endpoint may use from now on.
        :raises MCPEndpointDoesNotBelongToUser: When the endpoint isn't the user's.
        :raises MCPToolsNotAvailable: When a name isn't an enabled tool.
        :return: The updated endpoint.
        """

        if not user.id == endpoint.user_id:
            raise MCPEndpointDoesNotBelongToUser(
                "The user is not authorized to update the endpoint."
            )

        stored = mcp_tool_registry.get_allowed_names(endpoint)
        if set(names) - set(stored):
            CoreHandler().check_permissions(
                user,
                UpdateMCPEndpointOperationType.type,
                workspace=endpoint.workspace,
                context=endpoint.workspace,
            )

        enabled = {tool.name for tool in mcp_tool_registry.get_enabled_tools()}
        hidden = [name for name in stored if name not in enabled]
        endpoint.allowed_tools = self._check_tools(names) + hidden
        endpoint.save(update_fields=["allowed_tools"])
        return endpoint

    def _check_tools(self, names: list[str]) -> list[str]:
        """
        Returns the names in registry order, so the result doesn't depend on the
        request's order.

        :raises MCPToolsNotAvailable: When a name isn't an enabled tool.
        """

        requested = set(names)
        enabled = [t.name for t in mcp_tool_registry.get_enabled_tools()]
        unknown = sorted(requested - set(enabled))
        if unknown:
            raise MCPToolsNotAvailable(unknown)
        return [name for name in enabled if name in requested]

    def delete_endpoint(self, user: AbstractUser, endpoint: MCPEndpoint):
        """
        Deletes an existing MCP endpoint

        :param user: The user on whose behalf the endpoint is deleted.
        :param endpoint: The endpoint object that needs to be deleted.
        :raises MCPEndpointDoesNotBelongToUser: When the provided endpoint does not
            belong the provided user.
        """

        if not user.id == endpoint.user_id:
            raise MCPEndpointDoesNotBelongToUser(
                "The user is not authorized to delete the endpoint."
            )

        CoreHandler().check_permissions(
            user,
            DeleteMCPEndpointOperationType.type,
            workspace=endpoint.workspace,
            context=endpoint.workspace,
        )

        endpoint.delete()

    def get_oauth_grant(
        self, user: AbstractUser, grant_id: int, base_queryset: QuerySet = None
    ) -> MCPEndpoint:
        """
        Fetches one of the user's OAuth grants. There is no permission check: a
        user can always see and disconnect what they connected.

        :param base_queryset: The queryset to select the grant from, for example
            to lock it.
        :raises MCPEndpointDoesNotExist: When the user has no grant with that id.
        """

        if base_queryset is None:
            base_queryset = MCPEndpoint.objects

        try:
            return base_queryset.select_related("workspace").get(
                id=grant_id, user=user, oauth_client_id__isnull=False
            )
        except MCPEndpoint.DoesNotExist:
            raise MCPEndpointDoesNotExist(
                f"The MCP OAuth grant with id {grant_id} does not exist."
            )

    def disconnect_oauth_grant(self, endpoint: MCPEndpoint):
        """
        Deletes an OAuth grant from `get_oauth_grant`, which revokes its tokens.
        Skips the MCP endpoint permission checks, so losing them never keeps a
        client connected.
        """

        endpoint.delete()

    def revoke_workspace_grants(self, user_id: int, workspace_id: int) -> None:
        """
        Deletes the user's OAuth grants in the workspace and their tokens, without
        a permission check, for when the user is no longer a member.
        """

        MCPEndpoint.objects.filter(
            user_id=user_id, workspace_id=workspace_id, oauth_client_id__isnull=False
        ).delete()
