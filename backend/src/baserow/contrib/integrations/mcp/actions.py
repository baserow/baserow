from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import ActionType, ActionTypeDescription
from baserow.core.action.scopes import ApplicationActionScopeType

from .models import MCPServerIntegration
from .service import MCPServerService

MCP_SERVER_ACTION_CONTEXT = _(
    'in application "%(application_name)s" (%(application_id)s).'
)


def _register(
    action_type: type[ActionType],
    user: AbstractUser,
    integration: MCPServerIntegration,
    **params,
) -> None:
    application = integration.application
    action_type.register_action(
        user=user,
        params=action_type.Params(
            integration_id=integration.id,
            integration_name=integration.name,
            application_id=application.id,
            application_name=application.name,
            **params,
        ),
        scope=ApplicationActionScopeType.value(application.id),
        workspace=application.workspace,
    )


class UpdateMCPServerToolsActionType(ActionType):
    """Turns tools of an MCP server on or off. Audited, not undoable."""

    type = "update_mcp_server_tools"
    description = ActionTypeDescription(
        _("Update MCP server tools"),
        _('Tools of MCP server "%(integration_name)s" (%(integration_id)s) updated'),
        MCP_SERVER_ACTION_CONTEXT,
    )
    analytics_params = ["integration_id", "application_id"]

    @dataclass
    class Params:
        integration_id: int
        integration_name: str
        application_id: int
        application_name: str
        enabled_tools: list[str]
        tools_changing_data: list[str]

    @classmethod
    def do(
        cls, user: AbstractUser, integration_id: int, tools: list[dict]
    ) -> MCPServerIntegration:
        """
        :param user: Who changes the tools.
        :param integration_id: The MCP server.
        :param tools: Per tool, its name and the values to change.
        :return: The server, with its stored tools.
        """

        # Registered before the commit sends the change to other editors, so
        # a failure there can't leave a change without its audit entry.
        with transaction.atomic():
            integration = MCPServerService().update_tools(user, integration_id, tools)
            stored = [tool for tool in integration.tools.all() if not tool.removed]
            _register(
                cls,
                user,
                integration,
                enabled_tools=[tool.name for tool in stored if tool.enabled],
                tools_changing_data=[tool.name for tool in stored if tool.changes_data],
            )
        return integration

    @classmethod
    def scope(cls, application_id: int) -> str:
        return ApplicationActionScopeType.value(application_id)


class ConnectMCPServerAccountActionType(ActionType):
    """Connects an account to an MCP server that uses OAuth."""

    type = "connect_mcp_server_account"
    description = ActionTypeDescription(
        _("Connect MCP server account"),
        _(
            'Account connected to MCP server "%(integration_name)s" (%(integration_id)s)'
        ),
        MCP_SERVER_ACTION_CONTEXT,
    )
    analytics_params = ["integration_id", "application_id"]

    @dataclass
    class Params:
        integration_id: int
        integration_name: str
        application_id: int
        application_name: str

    @classmethod
    def do(cls, user: AbstractUser, state: str, code: str) -> MCPServerIntegration:
        """
        :param user: Who finishes the sign-in.
        :param state: The state the provider redirected back with.
        :param code: The authorization code, empty when cancelled.
        :return: The connected server.
        """

        # The token exchange happens outside a transaction; the audit entry is
        # registered before other editors are told, as for the other actions.
        integration = MCPServerService().complete_oauth(user, state, code)
        with transaction.atomic():
            integration = MCPServerService().notify_updated(user, integration.id)
            _register(cls, user, integration)
        return integration

    @classmethod
    def scope(cls, application_id: int) -> str:
        return ApplicationActionScopeType.value(application_id)


class DisconnectMCPServerAccountActionType(ActionType):
    """Forgets the account connected to an MCP server."""

    type = "disconnect_mcp_server_account"
    description = ActionTypeDescription(
        _("Disconnect MCP server account"),
        _(
            'Account disconnected from MCP server "%(integration_name)s" '
            "(%(integration_id)s)"
        ),
        MCP_SERVER_ACTION_CONTEXT,
    )
    analytics_params = ["integration_id", "application_id"]

    @dataclass
    class Params:
        integration_id: int
        integration_name: str
        application_id: int
        application_name: str

    @classmethod
    def do(cls, user: AbstractUser, integration_id: int) -> MCPServerIntegration:
        """
        :param user: Who disconnects the account.
        :param integration_id: The MCP server.
        :return: The server.
        """

        with transaction.atomic():
            integration = MCPServerService().disconnect_oauth(user, integration_id)
            _register(cls, user, integration)
        return integration

    @classmethod
    def scope(cls, application_id: int) -> str:
        return ApplicationActionScopeType.value(application_id)
