import dataclasses

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.api.sessions import get_untrusted_client_session_id
from baserow.core import posthog
from baserow.core.action.registries import ActionType, ActionTypeDescription
from baserow.core.action.scopes import (
    WORKSPACE_ACTION_CONTEXT,
    WorkspaceActionScopeType,
)
from baserow.core.models import Workspace

from .handler import MCPEndpointHandler
from .models import MCPEndpoint
from .registries import mcp_tool_registry


class CreateMCPEndpointActionType(ActionType):
    type = "create_mcp_endpoint"
    description = ActionTypeDescription(
        _("Create MCP endpoint"),
        _(
            'An MCP Endpoint with name "%(endpoint_name)s" (%(endpoint_id)s) has been created'
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "endpoint_id",
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        endpoint_id: int
        endpoint_name: str
        endpoint_key: str
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(cls, user: AbstractUser, workspace: Workspace, name: str):
        endpoint = MCPEndpointHandler().create_endpoint(user, workspace, name)
        cls.register_action(
            user,
            cls.Params(
                endpoint.id, endpoint.name, endpoint.key, workspace.id, workspace.name
            ),
            cls.scope(workspace.id),
            workspace,
        )
        return endpoint

    @classmethod
    def scope(cls, workspace_id: int):
        return WorkspaceActionScopeType.value(workspace_id)


class UpdateMCPEndpointActionType(ActionType):
    type = "update_mcp_endpoint"
    description = ActionTypeDescription(
        _("Update MCP endpoint name"),
        _(
            'The MCP Endpoint (%(endpoint_id)s) name changed from "%(original_endpoint_name)s" to "%(endpoint_name)s"'
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "endpoint_id",
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        endpoint_id: int
        endpoint_name: str
        workspace_id: int
        workspace_name: str
        original_endpoint_name: str

    @classmethod
    def do(cls, user: AbstractUser, endpoint: MCPEndpoint, name: str):
        original_endpoint_name = endpoint.name
        workspace = endpoint.workspace

        endpoint = MCPEndpointHandler().update_endpoint(user, endpoint, name)

        cls.register_action(
            user,
            cls.Params(
                endpoint.id,
                endpoint.name,
                workspace.id,
                workspace.name,
                original_endpoint_name,
            ),
            cls.scope(workspace.id),
            workspace,
        )
        return endpoint

    @classmethod
    def scope(cls, workspace_id: int):
        return WorkspaceActionScopeType.value(workspace_id)


class DeleteMCPEndpointActionType(ActionType):
    type = "delete_mcp_endpoint"
    description = ActionTypeDescription(
        _("Delete MCP endpoint"),
        _('The MCP Endpoint "%(endpoint_name)s" (%(endpoint_id)s) has been deleted'),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "endpoint_id",
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        endpoint_id: int
        endpoint_name: str
        endpoint_key: str
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        endpoint: MCPEndpoint,
    ):
        workspace = endpoint.workspace
        endpoint_id = endpoint.id
        endpoint_name = endpoint.name
        endpoint_key = endpoint.key

        MCPEndpointHandler().delete_endpoint(user, endpoint)

        cls.register_action(
            user,
            cls.Params(
                endpoint_id, endpoint_name, endpoint_key, workspace.id, workspace.name
            ),
            cls.scope(workspace.id),
            workspace,
        )

    @classmethod
    def scope(cls, workspace_id: int):
        return WorkspaceActionScopeType.value(workspace_id)


class ConnectMCPOAuthClientActionType(ActionType):
    type = "connect_mcp_oauth_client"
    description = ActionTypeDescription(
        _("Connect app to MCP"),
        _(
            '"%(client_name)s" was connected to the MCP server with %(tool_count)s tools'
        ),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "endpoint_id",
        "workspace_id",
    ]
    # Sent from `do` once the consent commits: it runs inside the consent
    # transaction, which rolls back if no code is issued.
    capture_analytics_event = False

    @dataclasses.dataclass
    class Params:
        endpoint_id: int
        client_id: str
        client_name: str
        workspace_id: int
        workspace_name: str
        allowed_tools: list[str]
        tool_count: int
        reconnect: bool

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        workspace: Workspace,
        client_id: str,
        name: str,
        allowed_tools: list[str],
    ) -> MCPEndpoint:
        # The handler doesn't say whether it created the grant, and it runs
        # inside the consent transaction, so checking first is consistent.
        reconnect = MCPEndpoint.objects.filter(
            user=user, workspace=workspace, oauth_client_id=client_id
        ).exists()
        endpoint = MCPEndpointHandler().grant_oauth_client(
            user, workspace, client_id, name, allowed_tools
        )
        params = cls.Params(
            endpoint.id,
            client_id,
            name,
            workspace.id,
            workspace.name,
            allowed_tools,
            len(mcp_tool_registry.get_allowed_tools(endpoint)),
            reconnect,
        )
        cls.register_action(user, params, cls.scope(workspace.id), workspace)

        properties = cls.get_analytics_properties(dataclasses.asdict(params))
        session = get_untrusted_client_session_id(user)
        transaction.on_commit(
            lambda: posthog.capture_user_event(
                user, cls.type, properties, workspace=workspace, session=session
            )
        )
        return endpoint

    @classmethod
    def scope(cls, workspace_id: int):
        return WorkspaceActionScopeType.value(workspace_id)


class DisconnectMCPOAuthClientActionType(ActionType):
    type = "disconnect_mcp_oauth_client"
    description = ActionTypeDescription(
        _("Disconnect app from MCP"),
        _('"%(client_name)s" was disconnected from the MCP server'),
        WORKSPACE_ACTION_CONTEXT,
    )
    analytics_params = [
        "endpoint_id",
        "workspace_id",
    ]

    @dataclasses.dataclass
    class Params:
        endpoint_id: int
        client_id: str
        client_name: str
        workspace_id: int
        workspace_name: str

    @classmethod
    def do(cls, user: AbstractUser, endpoint: MCPEndpoint):
        workspace = endpoint.workspace
        params = cls.Params(
            endpoint.id,
            endpoint.oauth_client_id,
            endpoint.name,
            workspace.id,
            workspace.name,
        )

        MCPEndpointHandler().disconnect_oauth_grant(user, endpoint)

        cls.register_action(user, params, cls.scope(workspace.id), workspace)

    @classmethod
    def scope(cls, workspace_id: int):
        return WorkspaceActionScopeType.value(workspace_id)
