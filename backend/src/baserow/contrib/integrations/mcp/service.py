from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.core.handler import CoreHandler
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.operations import UpdateIntegrationOperationType

from .exceptions import MCPOAuthStateInvalid
from .handler import MCPServerHandler, MCPToolSettings
from .models import MCPAuthType, MCPServerIntegration


class MCPServerService:
    def get_server_for_update(
        self, user: AbstractUser, integration_id: int
    ) -> MCPServerIntegration:
        """
        Return the MCP server if the user may change it.

        :param user: Who asks.
        :param integration_id: The integration.
        :raises IntegrationDoesNotExist: When it doesn't exist or isn't an MCP
            server.
        :return: The server.
        """

        integration = IntegrationHandler().get_integration(integration_id).specific
        if not isinstance(integration, MCPServerIntegration):
            raise IntegrationDoesNotExist()
        CoreHandler().check_permissions(
            user,
            UpdateIntegrationOperationType.type,
            workspace=integration.application.workspace,
            context=integration,
        )
        return integration

    def refresh_tools(self, user: AbstractUser, integration_id: int):
        """
        List the server's tools and store them. The permission check and the
        network call happen outside a transaction, the store inside one.

        :param user: Who asks.
        :param integration_id: The integration.
        :raises MCPServerUnreachable: When the server can't list its tools.
        :return: The server, with its stored tools.
        """

        integration = self.get_server_for_update(user, integration_id)
        definitions = MCPServerHandler().fetch_remote_tools(integration)
        with transaction.atomic():
            # Checked again: access may have changed while the server answered.
            integration = self.get_server_for_update(user, integration_id)
            MCPServerHandler().store_tools(integration, definitions)
        return self._reload(integration_id)

    def update_tools(
        self, user: AbstractUser, integration_id: int, tools: list[dict]
    ) -> MCPServerIntegration:
        with transaction.atomic():
            integration = self.get_server_for_update(user, integration_id)
            MCPServerHandler().update_tools(
                integration, [MCPToolSettings(**tool) for tool in tools]
            )
        return self._reload(integration_id)

    def start_oauth(self, user: AbstractUser, integration_id: int) -> str:
        """
        Start connecting an account to a server that uses OAuth.

        :raises MCPOAuthFailed: When the server doesn't support OAuth sign-in.
        :return: Where to send the editor to sign in.
        """

        integration = self.get_server_for_update(user, integration_id)
        if integration.auth_type != MCPAuthType.OAUTH:
            raise IntegrationDoesNotExist()
        return MCPServerHandler().start_oauth(integration, user)

    def complete_oauth(self, state: str, code: str) -> MCPServerIntegration:
        """
        Finish an authorization when the provider redirects back. The request
        carries no Baserow session, so the editor is the one who started it, and
        they must still be allowed to change the server.

        :raises MCPOAuthStateInvalid: When the state is unknown or expired.
        :raises MCPOAuthFailed: When the token exchange fails.
        """

        pending = MCPServerHandler().pop_oauth_state(state)
        user = get_user_model().objects.filter(id=pending["user_id"]).first()
        if user is None or not code:
            raise MCPOAuthStateInvalid()
        integration = self.get_server_for_update(user, pending["integration_id"])
        return MCPServerHandler().complete_oauth(integration, user, pending, code)

    def disconnect_oauth(
        self, user: AbstractUser, integration_id: int
    ) -> MCPServerIntegration:
        with transaction.atomic():
            integration = self.get_server_for_update(user, integration_id)
            MCPServerHandler().disconnect_oauth(integration)
        return self._reload(integration_id)

    def _reload(self, integration_id: int) -> MCPServerIntegration:
        """Read the server again, so its prefetched tools are the stored ones."""

        return IntegrationHandler().get_integration(integration_id).specific
