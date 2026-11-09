"""
OAuth for MCP servers, with Baserow as the client.

The MCP SDK's own OAuth provider runs the whole flow inside one request, which
suits a desktop app. A web app needs it split in two: discovery, registration
and the authorization URL when an editor clicks Connect, and the token exchange
when the provider redirects back. This module does those steps with the SDK's
discovery and registration helpers, over the same address-checking HTTP client
as the MCP connection itself, so discovery can't be pointed at private
addresses either.
"""

import base64
import hashlib
import secrets
import time
from dataclasses import asdict, dataclass, field
from urllib.parse import quote, urlencode, urlparse

from django.conf import settings
from django.urls import reverse

import httpx
from loguru import logger
from mcp.client.auth.utils import (
    build_oauth_authorization_server_metadata_discovery_urls,
    build_protected_resource_metadata_discovery_urls,
    create_client_registration_request,
    create_oauth_metadata_request,
    extract_resource_metadata_from_www_auth,
    extract_scope_from_www_auth,
    get_client_metadata_scopes,
    handle_auth_metadata_response,
    handle_protected_resource_response,
    handle_registration_response,
    is_valid_client_metadata_url,
    validate_metadata_issuer,
)
from mcp.shared.auth import OAuthClientMetadata, OAuthMetadata, OAuthToken
from mcp.shared.auth_utils import check_resource_allowed, resource_url_from_server_url
from mcp.types import LATEST_PROTOCOL_VERSION
from pydantic import AnyHttpUrl

from .exceptions import MCPOAuthFailed
from .http import create_mcp_http_client
from .models import MCPOAuthClientSource

CLIENT_NAME = "Baserow"
# Refresh a token this many seconds before it expires, so a reply that starts
# just before expiry doesn't fail halfway.
REFRESH_MARGIN_SECONDS = 300


# The frontend page the provider sends the editor back to. It hands the code to
# Baserow with the editor's own session, so only they can finish their sign-in.
REDIRECT_PATH = "/agent/mcp-oauth-callback"


def get_redirect_uri() -> str:
    return settings.PUBLIC_WEB_FRONTEND_URL.rstrip("/") + REDIRECT_PATH


def get_client_metadata_url() -> str | None:
    """
    The URL of Baserow's client metadata document, used as its client id with
    authorization servers that support it. Only an https URL qualifies, so
    instances on plain http register dynamically instead.
    """

    url = settings.PUBLIC_BACKEND_URL.rstrip("/") + reverse(
        "api:mcp_server:oauth_client_metadata"
    )
    return url if is_valid_client_metadata_url(url) else None


def get_client_metadata() -> dict:
    """The client metadata document, also sent on dynamic registration."""

    return {
        "client_id": get_client_metadata_url(),
        "client_name": CLIENT_NAME,
        "client_uri": settings.PUBLIC_WEB_FRONTEND_URL,
        "redirect_uris": [get_redirect_uri()],
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }


@dataclass
class OAuthServer:
    """What discovery found, stored on the integration to refresh tokens."""

    issuer: str
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str | None = None
    resource: str | None = None
    scope: str | None = None
    supports_client_metadata_document: bool = False
    token_endpoint_auth_methods: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OAuthServer":
        names = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in names})


@dataclass
class OAuthClient:
    client_id: str
    client_secret: str
    source: str
    # How the client authenticates at the token endpoint.
    auth_method: str


@dataclass
class PendingAuthorization:
    authorization_url: str
    code_verifier: str


def _origin(url: str) -> str:
    """The URL's origin, rendered the way issuer URLs are, to compare them."""

    parsed = urlparse(url)
    return str(AnyHttpUrl(f"{parsed.scheme}://{parsed.netloc}"))


async def _send_metadata_request(client: httpx.AsyncClient, url: str):
    try:
        return await client.send(create_oauth_metadata_request(url))
    except httpx.HTTPError as exc:
        raise MCPOAuthFailed("The server's OAuth metadata could not be read.") from exc


async def discover(server_url: str) -> OAuthServer:
    """
    Find the authorization server of an MCP server: ask the server, which should
    answer 401 and point at its protected resource metadata, then read that
    and the authorization server's metadata.

    :param server_url: The MCP server's URL.
    :raises MCPOAuthFailed: When the server doesn't support OAuth.
    :return: The authorization server's endpoints.
    """

    async with create_mcp_http_client() as client:
        try:
            probe = await client.post(
                server_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": LATEST_PROTOCOL_VERSION,
                        "capabilities": {},
                        "clientInfo": {"name": CLIENT_NAME, "version": "1"},
                    },
                },
                headers={"Accept": "application/json, text/event-stream"},
            )
        except httpx.HTTPError as exc:
            raise MCPOAuthFailed("The MCP server could not be reached.") from exc

        resource_metadata = None
        for url in build_protected_resource_metadata_discovery_urls(
            extract_resource_metadata_from_www_auth(probe), server_url
        ):
            resource_metadata = await handle_protected_resource_response(
                await _send_metadata_request(client, url)
            )
            if resource_metadata:
                break

        resource = resource_url_from_server_url(server_url)
        if resource_metadata and resource_metadata.resource:
            advertised = str(resource_metadata.resource)
            if not check_resource_allowed(resource, advertised):
                raise MCPOAuthFailed(
                    "The server's metadata names a different resource."
                )
            resource = advertised

        authorization_server = (
            str(resource_metadata.authorization_servers[0])
            if resource_metadata and resource_metadata.authorization_servers
            else None
        )
        # Without resource metadata, older servers are their own issuer.
        issuer = authorization_server or _origin(server_url)
        metadata: OAuthMetadata | None = None
        for url in build_oauth_authorization_server_metadata_discovery_urls(
            authorization_server, server_url
        ):
            ok, metadata = await handle_auth_metadata_response(
                await _send_metadata_request(client, url)
            )
            if metadata or not ok:
                break
        if metadata is None:
            raise MCPOAuthFailed("The MCP server doesn't support OAuth sign-in.")
        try:
            validate_metadata_issuer(metadata, issuer)
        except Exception as exc:
            raise MCPOAuthFailed(str(exc)) from exc

    return OAuthServer(
        issuer=str(metadata.issuer),
        authorization_endpoint=str(metadata.authorization_endpoint),
        token_endpoint=str(metadata.token_endpoint),
        registration_endpoint=(
            str(metadata.registration_endpoint)
            if metadata.registration_endpoint
            else None
        ),
        # Only send a resource indicator to servers that publish resource
        # metadata; older ones may reject it.
        resource=resource if resource_metadata else None,
        scope=get_client_metadata_scopes(
            extract_scope_from_www_auth(probe), resource_metadata, metadata
        ),
        supports_client_metadata_document=bool(
            metadata.client_id_metadata_document_supported
        ),
        token_endpoint_auth_methods=list(
            metadata.token_endpoint_auth_methods_supported or []
        ),
    )


async def register(server: OAuthServer) -> OAuthClient:
    """
    Get a client id without an editor registering Baserow by hand: Baserow's
    client metadata document where the server accepts one, otherwise dynamic
    client registration.

    :raises MCPOAuthFailed: When the server supports neither.
    """

    metadata_url = get_client_metadata_url()
    if metadata_url and server.supports_client_metadata_document:
        return OAuthClient(
            client_id=metadata_url,
            client_secret="",
            source=MCPOAuthClientSource.METADATA_DOCUMENT,
            auth_method="none",
        )
    if not server.registration_endpoint:
        raise MCPOAuthFailed(
            "The server doesn't let Baserow register itself. Register Baserow "
            "with the server and enter its client id."
        )

    metadata = get_client_metadata()
    metadata.pop("client_id")
    client_metadata = OAuthClientMetadata.model_validate(
        {**metadata, "scope": server.scope}
    )
    async with create_mcp_http_client() as client:
        try:
            response = await client.send(
                create_client_registration_request(
                    OAuthMetadata.model_validate(
                        {
                            "issuer": server.issuer,
                            "authorization_endpoint": server.authorization_endpoint,
                            "token_endpoint": server.token_endpoint,
                            "registration_endpoint": server.registration_endpoint,
                        }
                    ),
                    client_metadata,
                    server.issuer,
                )
            )
            info = await handle_registration_response(response)
        except Exception as exc:
            raise MCPOAuthFailed(f"Registering Baserow failed: {exc}") from exc
    return OAuthClient(
        client_id=info.client_id,
        client_secret=info.client_secret or "",
        source=MCPOAuthClientSource.DYNAMIC,
        auth_method=info.token_endpoint_auth_method or "none",
    )


def manual_client_auth_method(server: OAuthServer, client_secret: str) -> str:
    """How an editor-registered client authenticates at the token endpoint."""

    if not client_secret:
        return "none"
    if "client_secret_post" in server.token_endpoint_auth_methods:
        return "client_secret_post"
    return "client_secret_basic"


def build_authorization(
    server: OAuthServer, client: OAuthClient, state: str
) -> PendingAuthorization:
    """
    The URL to send the editor to, with PKCE.

    :param state: Binds the redirect back to this authorization.
    """

    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    params = {
        "response_type": "code",
        "client_id": client.client_id,
        "redirect_uri": get_redirect_uri(),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if server.resource:
        params["resource"] = server.resource
    if server.scope:
        params["scope"] = server.scope
    separator = "&" if "?" in server.authorization_endpoint else "?"
    return PendingAuthorization(
        authorization_url=f"{server.authorization_endpoint}{separator}"
        f"{urlencode(params)}",
        code_verifier=verifier,
    )


async def _request_token(
    server: OAuthServer, client: OAuthClient, data: dict[str, str]
) -> OAuthToken:
    data = {**data, "client_id": client.client_id}
    if server.resource:
        data["resource"] = server.resource
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    if client.auth_method == "client_secret_basic" and client.client_secret:
        credentials = f"{quote(client.client_id, safe='')}:" + quote(
            client.client_secret, safe=""
        )
        headers["Authorization"] = (
            "Basic " + base64.b64encode(credentials.encode()).decode()
        )
    elif client.auth_method == "client_secret_post" and client.client_secret:
        data["client_secret"] = client.client_secret

    async with create_mcp_http_client() as http:
        try:
            response = await http.post(
                server.token_endpoint, data=data, headers=headers
            )
        except httpx.HTTPError as exc:
            raise MCPOAuthFailed(
                "The authorization server could not be reached.", retryable=True
            ) from exc
    if response.status_code != 200:
        logger.info(
            "MCP OAuth token request failed with status {}", response.status_code
        )
        raise MCPOAuthFailed(
            f"The authorization server refused the request ({response.status_code}).",
            retryable=response.status_code == 429 or response.status_code >= 500,
        )
    try:
        return OAuthToken.model_validate_json(response.content)
    except Exception as exc:
        raise MCPOAuthFailed("The authorization server's answer is invalid.") from exc


async def exchange_code(
    server: OAuthServer, client: OAuthClient, code: str, code_verifier: str
) -> OAuthToken:
    return await _request_token(
        server,
        client,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": get_redirect_uri(),
            "code_verifier": code_verifier,
        },
    )


async def refresh(
    server: OAuthServer, client: OAuthClient, refresh_token: str
) -> OAuthToken:
    return await _request_token(
        server,
        client,
        {"grant_type": "refresh_token", "refresh_token": refresh_token},
    )


def expires_soon(expires_at) -> bool:
    return expires_at is not None and (
        expires_at.timestamp() - time.time() < REFRESH_MARGIN_SECONDS
    )
