import dataclasses

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import ActionType, ActionTypeDescription
from baserow.core.action.scopes import (
    WORKSPACE_ACTION_CONTEXT,
    WorkspaceActionScopeType,
)
from baserow.core.models import Workspace

from .handler import MCPEndpointHandler
from .models import MCPEndpoint


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
