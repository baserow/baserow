import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from asgiref.sync import async_to_sync
from loguru import logger
from mcp.shared.auth import OAuthToken

from . import oauth
from .client import (
    MCPServerConnection,
    MCPToolDefinition,
    fetch_tools,
    refused_credential,
)
from .exceptions import (
    MCPOAuthFailed,
    MCPOAuthStateInvalid,
    MCPServerNotConnected,
    MCPServerRefusedCredential,
    MCPServerUnreachable,
)
from .models import (
    MCPAuthType,
    MCPOAuthClientSource,
    MCPServerIntegration,
    MCPServerTool,
)

# How long an editor has to finish signing in with the MCP server's provider.
OAUTH_STATE_TIMEOUT_SECONDS = 600
OAUTH_STATE_CACHE_KEY = "mcp_oauth_state:{}"
OAUTH_TOKEN_FIELDS = [
    "oauth_access_token",
    "oauth_refresh_token",
    "oauth_expires_at",
    "oauth_connected_at",
    "oauth_connected_by",
]
# Matches `MCPServerTool.name`. Longer names can't be stored.
MAX_TOOL_NAME_LENGTH = 128


@dataclass(frozen=True)
class MCPToolSettings:
    name: str
    enabled: bool | None = None
    changes_data: bool | None = None


class MCPServerHandler:
    def fetch_remote_tools(
        self, integration: MCPServerIntegration
    ) -> list[MCPToolDefinition]:
        """
        Ask the server for its tools. Never call this inside a transaction: the
        server may take a while to answer.

        :param integration: The server.
        :raises MCPServerNotConnected: When it uses OAuth and isn't connected.
        :raises MCPServerUnreachable: When the server can't be reached or fails.
        :return: The tools the server lists.
        """

        connection = self.get_connection(integration)
        try:
            return async_to_sync(fetch_tools)(connection)
        except Exception as exc:
            logger.info(
                "MCP server {} tools could not be listed ({})",
                integration.id,
                type(exc).__name__,
            )
            if refused_credential(exc):
                raise MCPServerRefusedCredential() from exc
            raise MCPServerUnreachable() from exc

    def store_tools(
        self,
        integration: MCPServerIntegration,
        definitions: list[MCPToolDefinition],
    ) -> list[MCPServerTool]:
        """
        Replace the stored snapshot with the server's current tools. New tools
        start off. A tool that is on and changed is turned off and flagged, so an
        editor reviews it before the Agent can call it again. A tool the server no
        longer lists is kept, marked removed and off, so turning it back on later
        is a deliberate choice.

        :param integration: The server.
        :param definitions: Its tools, as just listed.
        :return: The stored tools, in the server's order.
        """

        with transaction.atomic():
            existing = {
                tool.name: tool
                for tool in MCPServerTool.objects.select_for_update().filter(
                    integration=integration
                )
            }
            listed = set()
            to_create, to_update = [], []
            for order, definition in enumerate(definitions):
                if (
                    len(definition.name) > MAX_TOOL_NAME_LENGTH
                    or definition.name in listed
                ):
                    logger.info(
                        "MCP server {} listed a tool with a duplicate or too long "
                        "name, left out",
                        integration.id,
                    )
                    continue
                listed.add(definition.name)
                values = {
                    "title": definition.title[:255],
                    "description": definition.description,
                    "input_schema": definition.input_schema,
                    "annotations": definition.annotations,
                    "definition_hash": definition.definition_hash,
                    "order": order,
                    "removed": False,
                }
                tool = existing.get(definition.name)
                if tool is None:
                    to_create.append(
                        MCPServerTool(
                            integration=integration, name=definition.name, **values
                        )
                    )
                    continue
                if tool.definition_hash != definition.definition_hash and tool.enabled:
                    tool.enabled = False
                    tool.changed_since_review = True
                for key, value in values.items():
                    setattr(tool, key, value)
                to_update.append(tool)
            for name, tool in existing.items():
                if name not in listed:
                    tool.removed = True
                    tool.enabled = False
                    # A removed tool can't be reviewed, so it doesn't ask for it.
                    tool.changed_since_review = False
                    to_update.append(tool)

            MCPServerTool.objects.bulk_create(to_create)
            MCPServerTool.objects.bulk_update(
                to_update,
                [
                    "title",
                    "description",
                    "input_schema",
                    "annotations",
                    "definition_hash",
                    "order",
                    "removed",
                    "enabled",
                    "changed_since_review",
                ],
            )
        return list(integration.tools.all())

    def refresh_tools(self, integration: MCPServerIntegration) -> list[MCPServerTool]:
        return self.store_tools(integration, self.fetch_remote_tools(integration))

    def update_tools(
        self, integration: MCPServerIntegration, settings: list[MCPToolSettings]
    ) -> list[MCPServerTool]:
        """
        Turn tools on or off and say whether they change data. Saving a tool
        marks its current definition as reviewed.

        :param integration: The server.
        :param settings: Per tool, the values to change. Unknown names are
            ignored, and a removed tool can't be turned on.
        :return: The stored tools.
        """

        by_name = {setting.name: setting for setting in settings}
        with transaction.atomic():
            tools = list(
                MCPServerTool.objects.select_for_update().filter(
                    integration=integration, name__in=by_name.keys()
                )
            )
            for tool in tools:
                setting = by_name[tool.name]
                if setting.enabled is not None:
                    tool.enabled = setting.enabled and not tool.removed
                if setting.changes_data is not None:
                    tool.changes_data = setting.changes_data
                tool.changed_since_review = False
            MCPServerTool.objects.bulk_update(
                tools, ["enabled", "changes_data", "changed_since_review"]
            )
        return list(integration.tools.all())

    def get_connection(self, integration: MCPServerIntegration) -> MCPServerConnection:
        """
        The connection with a valid credential, refreshing an OAuth token that
        expires soon.

        :raises MCPServerNotConnected: When it uses OAuth and no account is
            connected, or the token can't be refreshed.
        """

        if integration.auth_type == MCPAuthType.OAUTH:
            if not integration.oauth_connected:
                raise MCPServerNotConnected()
            if oauth.expires_soon(integration.oauth_expires_at):
                self.refresh_oauth_token(integration)
        return MCPServerConnection.from_integration(integration)

    def refresh_oauth_token(self, integration: MCPServerIntegration) -> None:
        """
        Refresh the access token, once even when replies start at the same
        time: providers that rotate refresh tokens accept each one only once.
        The integration is updated in place.

        :raises MCPServerNotConnected: When the provider refuses, so an editor
            has to connect again.
        """

        failure = None
        with transaction.atomic():
            locked = MCPServerIntegration.objects.select_for_update().get(
                id=integration.id
            )
            if locked.oauth_connected and not oauth.expires_soon(
                locked.oauth_expires_at
            ):
                # Another reply refreshed it while this one waited for the lock.
                self._copy_tokens(locked, integration)
                return
            if not locked.oauth_refresh_token:
                raise MCPServerNotConnected()
            try:
                token = async_to_sync(oauth.refresh)(
                    oauth.OAuthServer.from_dict(locked.oauth_server),
                    self._oauth_client(locked),
                    locked.oauth_refresh_token,
                )
            except MCPOAuthFailed as exc:
                logger.info(
                    "MCP server {} token refresh failed: {}", locked.id, exc.message
                )
                if exc.retryable:
                    # The provider is down: the refresh token may still be good.
                    raise MCPServerNotConnected() from exc
                # Committed, not rolled back: the account must be connected again.
                locked.clear_oauth_tokens()
                failure = exc
            else:
                self._store_token(locked, token)
            locked.save(update_fields=OAUTH_TOKEN_FIELDS)
        self._copy_tokens(locked, integration)
        if failure:
            raise MCPServerNotConnected() from failure

    def start_oauth(self, integration: MCPServerIntegration, user: AbstractUser) -> str:
        """
        Find the server's authorization server, get Baserow a client id there,
        and return where to send the editor to sign in. Never call this inside
        a transaction: it talks to the server.

        :raises MCPOAuthFailed: When the server doesn't support OAuth sign-in or
            Baserow can't register.
        :return: The authorization URL.
        """

        server = async_to_sync(oauth.discover)(integration.url)
        stored = integration.oauth_server or {}
        if integration.oauth_client_source == MCPOAuthClientSource.MANUAL:
            client = oauth.OAuthClient(
                client_id=integration.oauth_client_id,
                client_secret=integration.oauth_client_secret,
                source=MCPOAuthClientSource.MANUAL,
                auth_method=oauth.manual_client_auth_method(
                    server, integration.oauth_client_secret
                ),
            )
        elif (
            integration.oauth_client_id
            and stored.get("issuer") == server.issuer
            and stored.get("client_auth_method")
        ):
            # Registered earlier with the same authorization server.
            client = self._oauth_client(integration)
        else:
            client = async_to_sync(oauth.register)(server)

        integration.oauth_server = {
            **server.to_dict(),
            "client_auth_method": client.auth_method,
        }
        integration.oauth_client_id = client.client_id
        integration.oauth_client_secret = client.client_secret
        integration.oauth_client_source = client.source
        integration.save(
            update_fields=[
                "oauth_server",
                "oauth_client_id",
                "oauth_client_secret",
                "oauth_client_source",
            ]
        )

        state = secrets.token_urlsafe(32)
        pending = oauth.build_authorization(server, client, state)
        cache.set(
            OAUTH_STATE_CACHE_KEY.format(state),
            {
                "integration_id": integration.id,
                "user_id": user.id,
                "code_verifier": pending.code_verifier,
                "client_id": client.client_id,
                "url": integration.url,
            },
            OAUTH_STATE_TIMEOUT_SECONDS,
        )
        return pending.authorization_url

    def pop_oauth_state(self, state: str) -> dict:
        """
        The authorization a callback belongs to. Each one can be used once.

        :raises MCPOAuthStateInvalid: When it's unknown, used or expired.
        """

        key = OAUTH_STATE_CACHE_KEY.format(state)
        pending = cache.get(key) if state else None
        if not pending:
            raise MCPOAuthStateInvalid()
        cache.delete(key)
        return pending

    def complete_oauth(
        self,
        integration: MCPServerIntegration,
        user: AbstractUser,
        pending: dict,
        code: str,
    ) -> MCPServerIntegration:
        """
        Exchange the authorization code for tokens and store them.

        :raises MCPOAuthStateInvalid: When the server, its sign-in method or
            its client changed since the authorization started.
        :raises MCPOAuthFailed: When the exchange fails.
        """

        if (
            integration.auth_type != MCPAuthType.OAUTH
            or not integration.oauth_server
            or integration.url != pending.get("url")
            or integration.oauth_client_id != pending["client_id"]
        ):
            raise MCPOAuthStateInvalid()
        token = async_to_sync(oauth.exchange_code)(
            oauth.OAuthServer.from_dict(integration.oauth_server),
            self._oauth_client(integration),
            code,
            pending["code_verifier"],
        )
        self._store_token(integration, token)
        integration.oauth_connected_at = timezone.now()
        integration.oauth_connected_by = user
        integration.save(update_fields=OAUTH_TOKEN_FIELDS)
        return integration

    def disconnect_oauth(self, integration: MCPServerIntegration) -> None:
        integration.clear_oauth_tokens()
        integration.save(update_fields=OAUTH_TOKEN_FIELDS)

    def _oauth_client(self, integration: MCPServerIntegration) -> oauth.OAuthClient:
        return oauth.OAuthClient(
            client_id=integration.oauth_client_id,
            client_secret=integration.oauth_client_secret,
            source=integration.oauth_client_source,
            auth_method=(integration.oauth_server or {}).get(
                "client_auth_method", "none"
            ),
        )

    def _store_token(self, integration: MCPServerIntegration, token: OAuthToken):
        integration.oauth_access_token = token.access_token
        # A refresh may not return a new refresh token; the old one stays valid.
        if token.refresh_token:
            integration.oauth_refresh_token = token.refresh_token
        integration.oauth_expires_at = (
            timezone.now() + timedelta(seconds=token.expires_in)
            if token.expires_in
            else None
        )

    def _copy_tokens(self, source, target):
        for name in (
            "oauth_access_token",
            "oauth_refresh_token",
            "oauth_expires_at",
            "oauth_connected_at",
            "oauth_connected_by_id",
        ):
            setattr(target, name, getattr(source, name))
