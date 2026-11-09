import base64
import hashlib
import json
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, urlparse

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session


def make_server() -> FastMCP:
    server = FastMCP("test")

    @server.tool(title="Add numbers")
    def add(a: int, b: int) -> str:
        """Add two numbers."""

        return str(a + b)

    @server.tool()
    def fail() -> str:
        """Always fails."""

        raise ValueError("Nothing works today.")

    return server


def serve(mocker, server: FastMCP) -> list:
    """
    Answer every connection with the in-memory server instead of the network.

    :return: The connections that were opened.
    """

    opened = []

    @asynccontextmanager
    async def memory_session(connection):
        opened.append(connection)
        async with create_connected_server_and_client_session(server) as session:
            yield session

    mocker.patch("baserow.contrib.integrations.mcp.client.open_session", memory_session)
    mocker.patch(
        "baserow.contrib.integrations.mcp.toolset.open_session", memory_session
    )
    return opened


class FakeAuthorizationServer:
    """
    An MCP server that asks for OAuth, its resource metadata, and the
    authorization server behind it, answered through a mock HTTP transport.
    """

    SERVER_URL = "https://mcp.example.com/mcp"
    ISSUER = "https://auth.example.com"

    def __init__(self, registration=True, metadata_document=False):
        self.registration = registration
        self.metadata_document = metadata_document
        self.requests: list[httpx.Request] = []
        self.challenges: dict[str, str] = {}
        self.refresh_fails = False
        self.refresh_unavailable = False
        self.issued = 0
        # None leaves `expires_in` out of the token response.
        self.expires_in = 3600
        # None leaves `refresh_token` out of the token response.
        self.refresh_token = "refresh-1"
        # Registers a client with a secret, without saying how to send it.
        self.confidential = False

    def authorize(self, authorization_url: str) -> str:
        """Approve like the user would, and return the code."""

        params = parse_qs(urlparse(authorization_url).query)
        code = f"code-{len(self.challenges)}"
        self.challenges[code] = params["code_challenge"][0]
        return code

    def _token(self, form: dict) -> httpx.Response:
        if form["grant_type"] == "authorization_code":
            verifier = form["code_verifier"]
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                .decode()
                .rstrip("=")
            )
            if self.challenges.pop(form["code"], None) != challenge:
                return httpx.Response(400, json={"error": "invalid_grant"})
        elif self.refresh_unavailable:
            return httpx.Response(503)
        elif self.refresh_fails or form["refresh_token"] != "refresh-1":
            return httpx.Response(400, json={"error": "invalid_grant"})
        self.issued += 1
        token = {
            "access_token": f"access-{self.issued}",
            "token_type": "Bearer",
            "expires_in": self.expires_in,
            "refresh_token": self.refresh_token,
        }
        return httpx.Response(
            200, json={k: v for k, v in token.items() if v is not None}
        )

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if url == self.SERVER_URL:
            return httpx.Response(
                401,
                headers={
                    "WWW-Authenticate": 'Bearer resource_metadata="https://mcp.'
                    'example.com/.well-known/oauth-protected-resource/mcp"'
                },
            )
        if url == "https://mcp.example.com/.well-known/oauth-protected-resource/mcp":
            return httpx.Response(
                200,
                json={
                    "resource": self.SERVER_URL,
                    "authorization_servers": [self.ISSUER],
                    "scopes_supported": ["read", "write"],
                },
            )
        if url == f"{self.ISSUER}/.well-known/oauth-authorization-server":
            return httpx.Response(
                200,
                json={
                    "issuer": self.ISSUER,
                    "authorization_endpoint": f"{self.ISSUER}/authorize",
                    "token_endpoint": f"{self.ISSUER}/token",
                    "response_types_supported": ["code"],
                    "code_challenge_methods_supported": ["S256"],
                    "token_endpoint_auth_methods_supported": [
                        "none",
                        "client_secret_post",
                    ],
                    **(
                        {"registration_endpoint": f"{self.ISSUER}/register"}
                        if self.registration
                        else {}
                    ),
                    "client_id_metadata_document_supported": self.metadata_document,
                },
            )
        if url == f"{self.ISSUER}/register":
            registered = {
                **json.loads(request.content),
                "client_id": "registered-client",
                "token_endpoint_auth_method": "none",
            }
            if self.confidential:
                # Ignores the requested method and leaves it out of the reply.
                registered.pop("token_endpoint_auth_method")
                registered["client_secret"] = "registered-secret"
            return httpx.Response(201, json=registered)
        if url == f"{self.ISSUER}/token":
            return self._token(
                {
                    key: values[0]
                    for key, values in parse_qs(request.content.decode()).items()
                }
            )
        return httpx.Response(404)


def serve_oauth(mocker, server: FakeAuthorizationServer) -> FakeAuthorizationServer:
    mocker.patch(
        "baserow.contrib.integrations.mcp.oauth.create_mcp_http_client",
        lambda headers=None: httpx.AsyncClient(
            transport=httpx.MockTransport(server.handle), headers=headers
        ),
    )
    return server
