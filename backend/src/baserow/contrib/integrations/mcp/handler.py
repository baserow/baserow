import secrets
from dataclasses import asdict, dataclass, fields
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
    MCP_SERVER_LOCK_OF,
    MCPAuthType,
    MCPOAuthClientSource,
    MCPServerIntegration,
    MCPServerTool,
)

# How long an editor has to finish signing in with the MCP server's provider.
OAUTH_STATE_TIMEOUT_SECONDS = 600
OAUTH_STATE_CACHE_KEY = "mcp_oauth_state:{}"
# Assumed for an access token the provider gives no lifetime for.
DEFAULT_TOKEN_LIFETIME_SECONDS = 3600
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
    # The definition the editor reviewed. A tool changed since keeps waiting.
    definition_hash: str | None = None


@dataclass(frozen=True)
class PendingSignIn:
    """A sign-in an editor started, kept until the provider redirects back."""

    integration_id: int
    user_id: int
    code_verifier: str
    client_id: str
    # The connection it was started for: the server's URL and its OAuth
    # generation, which changes when it's set up differently or signed out.
    url: str
    generation: int

    @classmethod
    def from_dict(cls, data: dict) -> "PendingSignIn | None":
        """
        :param data: What was cached.
        :return: The sign-in, or None when it was cached by another version.
        """

        names = {field.name for field in fields(cls)}
        if not names <= data.keys():
            return None
        return cls(**{name: data[name] for name in names})

    def still_matches(self, integration: MCPServerIntegration) -> bool:
        """
        :param integration: The server as stored now.
        :return: Whether it's still the connection this sign-in was for.
        """

        return (
            integration.auth_type == MCPAuthType.OAUTH
            and bool(integration.oauth_server)
            and integration.url == self.url
            and integration.oauth_client_id == self.client_id
            and integration.oauth_generation == self.generation
        )


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
                    "title": definition.title,
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
        """
        List the server's tools and store them. Never call this inside a
        transaction: the server may take a while to answer.

        :param integration: The server.
        :raises MCPServerNotConnected: When it uses OAuth and isn't connected.
        :raises MCPServerUnreachable: When the server can't be reached or fails.
        :return: The stored tools.
        """

        return self.store_tools(integration, self.fetch_remote_tools(integration))

    def update_tools(
        self, integration: MCPServerIntegration, settings: list[MCPToolSettings]
    ) -> list[MCPServerTool]:
        """
        Turn tools on or off and say whether they change data. Saving a tool
        marks its current definition as reviewed.

        :param integration: The server.
        :param settings: Per tool, the values to change. Unknown names are
            ignored, a removed tool can't be turned on, and a tool whose
            definition changed since the editor saw it is left as it is.
        :return: The stored tools.
        """

        by_name = {setting.name: setting for setting in settings}
        with transaction.atomic():
            tools = list(
                MCPServerTool.objects.select_for_update().filter(
                    integration=integration, name__in=by_name.keys()
                )
            )
            tools = [
                tool
                for tool in tools
                if by_name[tool.name].definition_hash in (None, tool.definition_hash)
            ]
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
        The connection to use for the server, with a valid credential: an OAuth
        token that expires soon is refreshed first. Built from the stored row,
        so its URL and token always belong together.

        :param integration: The server, as the caller read it.
        :raises MCPServerNotConnected: When it uses OAuth and no account is
            connected, the token can't be refreshed, or the server was moved or
            signed out since the caller read it.
        :return: The connection.
        """

        if integration.auth_type == MCPAuthType.OAUTH:
            if not integration.oauth_connected:
                raise MCPServerNotConnected()
            if oauth.expires_soon(integration.oauth_expires_at):
                integration = self.refresh_oauth_token(integration)
        return self._build_connection(integration)

    def _build_connection(
        self, integration: MCPServerIntegration
    ) -> MCPServerConnection:
        """
        :param integration: The server, with a current credential.
        :return: Its URL and the headers that carry its credential.
        """

        headers = {}
        if integration.auth_type == MCPAuthType.OAUTH:
            if integration.oauth_access_token:
                headers["Authorization"] = f"Bearer {integration.oauth_access_token}"
        elif (
            integration.auth_type == MCPAuthType.HEADER
            and integration.auth_header_name
            and integration.auth_header_value
        ):
            headers[integration.auth_header_name] = integration.auth_header_value
        return MCPServerConnection(url=integration.url, headers=headers)

    def refresh_oauth_token(
        self, integration: MCPServerIntegration
    ) -> MCPServerIntegration:
        """
        Refresh the access token, once even when replies start at the same
        time: providers that rotate refresh tokens accept each one only once.
        A token that can't be refreshed and expired is cleared, so the server
        shows as not connected.

        :param integration: The server, as the caller read it.
        :raises MCPServerNotConnected: When the provider refuses, so an editor
            has to connect again, or the server was moved or signed out since
            the caller read it.
        :return: The stored server, with a current token.
        """

        failure = None
        with transaction.atomic():
            locked = MCPServerIntegration.objects.select_for_update(
                of=MCP_SERVER_LOCK_OF
            ).get(id=integration.id)
            if not self._same_connection(locked, integration):
                # Its tokens belong to another server or sign-in than the one
                # the caller is about to use.
                raise MCPServerNotConnected()
            if not oauth.expires_soon(locked.oauth_expires_at):
                # Refreshed, or signed in again, while this waited for the lock.
                return locked
            if not locked.oauth_refresh_token:
                if locked.oauth_expires_at > timezone.now():
                    return locked
                # Nothing to refresh with: an editor has to sign in again.
                locked.clear_oauth_tokens()
                failure = MCPServerNotConnected()
            else:
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
                    # Committed, not rolled back: the account must be connected
                    # again.
                    locked.clear_oauth_tokens()
                    failure = exc
                else:
                    self._store_token(locked, token)
            locked.save(update_fields=OAUTH_TOKEN_FIELDS)
        if failure:
            raise MCPServerNotConnected() from failure
        return locked

    def _same_connection(
        self, stored: MCPServerIntegration, read: MCPServerIntegration
    ) -> bool:
        """
        :param stored: The server as stored now.
        :param read: The server as read earlier.
        :return: Whether both are the same OAuth connection: not moved, signed
            out or set up differently in between.
        """

        return (
            stored.auth_type == MCPAuthType.OAUTH
            and stored.url == read.url
            and stored.oauth_generation == read.oauth_generation
        )

    def start_oauth(self, integration: MCPServerIntegration, user: AbstractUser) -> str:
        """
        Find the server's authorization server, get Baserow a client id there,
        and return where to send the editor to sign in. Never call this inside
        a transaction: it talks to the server.

        :param integration: The server, using OAuth.
        :param user: The editor signing in. Only they can finish it.
        :raises MCPOAuthFailed: When the server doesn't support OAuth sign-in,
            Baserow can't register, or the server was changed meanwhile.
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

        with transaction.atomic():
            locked = MCPServerIntegration.objects.select_for_update(
                of=MCP_SERVER_LOCK_OF
            ).get(id=integration.id)
            # What was discovered belongs to the server as it was read.
            if not self._same_connection(locked, integration):
                raise MCPOAuthFailed(
                    "The server was changed while signing in. Try again."
                )
            stored = locked.oauth_server or {}
            if (
                stored.get("issuer") != server.issuer
                or locked.oauth_client_id != client.client_id
            ):
                # The account was connected through another authorization
                # server or client: its tokens must not go to this one.
                locked.clear_oauth_tokens()
                locked.oauth_generation += 1
            locked.oauth_server = {
                **server.to_dict(),
                "client_auth_method": client.auth_method,
            }
            locked.oauth_client_id = client.client_id
            locked.oauth_client_secret = client.client_secret
            locked.oauth_client_source = client.source
            locked.save(
                update_fields=[
                    *OAUTH_TOKEN_FIELDS,
                    "oauth_generation",
                    "oauth_server",
                    "oauth_client_id",
                    "oauth_client_secret",
                    "oauth_client_source",
                ]
            )

        state = secrets.token_urlsafe(32)
        authorization = oauth.build_authorization(server, client, state)
        pending = PendingSignIn(
            integration_id=integration.id,
            user_id=user.id,
            code_verifier=authorization.code_verifier,
            client_id=client.client_id,
            url=locked.url,
            generation=locked.oauth_generation,
        )
        cache.set(
            OAUTH_STATE_CACHE_KEY.format(state),
            asdict(pending),
            OAUTH_STATE_TIMEOUT_SECONDS,
        )
        return authorization.authorization_url

    def pop_oauth_state(self, state: str, user: AbstractUser) -> "PendingSignIn":
        """
        The sign-in a callback belongs to. Each one can be used once, and only
        by the user who started it; anyone else's attempt leaves it be.

        :param state: The state the provider redirected back with.
        :param user: Who finishes the sign-in.
        :raises MCPOAuthStateInvalid: When it's unknown, used, expired or
            someone else's.
        :return: The pending sign-in.
        """

        key = OAUTH_STATE_CACHE_KEY.format(state)
        stored = cache.get(key) if state else None
        pending = PendingSignIn.from_dict(stored) if stored else None
        if pending is None or pending.user_id != user.id:
            raise MCPOAuthStateInvalid()
        # Only the request that deletes it may go on, if two arrive at once.
        if not cache.delete(key):
            raise MCPOAuthStateInvalid()
        return pending

    def complete_oauth(
        self,
        integration: MCPServerIntegration,
        user: AbstractUser,
        pending: "PendingSignIn",
        code: str,
    ) -> None:
        """
        Exchange the authorization code for tokens and store them.

        :param integration: The server the sign-in was started for.
        :param user: The editor who signed in.
        :param pending: The sign-in, from `pop_oauth_state`.
        :param code: The authorization code.
        :raises MCPOAuthStateInvalid: When the server, its sign-in method or
            its client changed, or it was signed out, since the sign-in started.
        :raises MCPOAuthFailed: When the exchange fails.
        """

        if not pending.still_matches(integration):
            raise MCPOAuthStateInvalid()
        token = async_to_sync(oauth.exchange_code)(
            oauth.OAuthServer.from_dict(integration.oauth_server),
            self._oauth_client(integration),
            code,
            pending.code_verifier,
        )
        with transaction.atomic():
            # Checked again: the server may have been moved while the provider
            # answered, and its tokens must not go to the new one.
            locked = MCPServerIntegration.objects.select_for_update(
                of=MCP_SERVER_LOCK_OF
            ).get(id=integration.id)
            if not pending.still_matches(locked):
                raise MCPOAuthStateInvalid()
            # A new sign-in may be another account: nothing of the old one stays.
            locked.oauth_refresh_token = ""
            self._store_token(locked, token)
            locked.oauth_connected_at = timezone.now()
            locked.oauth_connected_by = user
            locked.save(update_fields=OAUTH_TOKEN_FIELDS)

    def disconnect_oauth(self, integration: MCPServerIntegration) -> None:
        """
        Forget the connected account. A sign-in started before can't finish.

        :param integration: The server.
        """

        with transaction.atomic():
            locked = MCPServerIntegration.objects.select_for_update(
                of=MCP_SERVER_LOCK_OF
            ).get(id=integration.id)
            locked.clear_oauth_tokens()
            locked.oauth_generation += 1
            locked.save(update_fields=[*OAUTH_TOKEN_FIELDS, "oauth_generation"])

    def _oauth_client(self, integration: MCPServerIntegration) -> oauth.OAuthClient:
        """
        :param integration: The server, with its stored client.
        :return: How Baserow authenticates at its token endpoint.
        """

        server = integration.oauth_server or {}
        auth_method = server.get("client_auth_method", "none")
        if integration.oauth_client_source == MCPOAuthClientSource.MANUAL and server:
            # The editor may change their client's secret at any time.
            auth_method = oauth.manual_client_auth_method(
                oauth.OAuthServer.from_dict(server), integration.oauth_client_secret
            )
        return oauth.OAuthClient(
            client_id=integration.oauth_client_id,
            client_secret=integration.oauth_client_secret,
            source=integration.oauth_client_source,
            auth_method=auth_method,
        )

    def _store_token(
        self, integration: MCPServerIntegration, token: OAuthToken
    ) -> None:
        """
        Set a token the provider issued on the server, without saving.

        :param integration: The server.
        :param token: The provider's answer.
        """

        integration.oauth_access_token = token.access_token
        # A refresh may not return a new refresh token; the old one stays valid.
        if token.refresh_token:
            integration.oauth_refresh_token = token.refresh_token
        lifetime = token.expires_in
        if lifetime is None and integration.oauth_refresh_token:
            # The provider didn't say; refresh regularly rather than never.
            lifetime = DEFAULT_TOKEN_LIFETIME_SECONDS
        # Zero means already expired, so the token is refreshed or the account
        # connected again before it's ever sent.
        integration.oauth_expires_at = (
            timezone.now() + timedelta(seconds=lifetime)
            if lifetime is not None
            else None
        )
