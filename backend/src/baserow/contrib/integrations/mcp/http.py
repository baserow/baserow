import typing

from django.conf import settings

import anyio
import httpcore
import httpx
from httpcore._backends.auto import AutoBackend

from baserow.core.utils import resolve_and_validate_hostname

# Connect, write and pool timeouts. Reads may wait on a streamed response.
MCP_CONNECT_TIMEOUT = 10
MCP_READ_TIMEOUT = 60


class UnsafeMCPAddress(httpx.ConnectError):
    """The MCP server resolves to an address Baserow must not connect to."""


class _ValidatingNetworkBackend(httpcore.AsyncNetworkBackend):
    """
    Resolves the host itself, checks every address, and connects to a checked
    address. Checking and connecting to the same address means a DNS answer that
    changes between the two can't point the connection somewhere else. TLS still
    verifies the certificate against the original hostname, which httpcore passes
    separately when it starts TLS.
    """

    def __init__(self, allow_private: bool):
        self._allow_private = allow_private
        self._backend = AutoBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: typing.Iterable | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if self._allow_private:
            # Like the HTTP request integration with private addresses allowed:
            # no checks at all, so local servers work on self-hosted instances.
            return await self._backend.connect_tcp(
                host,
                port,
                timeout=timeout,
                local_address=local_address,
                socket_options=socket_options,
            )
        try:
            addresses = await anyio.to_thread.run_sync(
                resolve_and_validate_hostname, host, False
            )
        except ValueError as exc:
            raise UnsafeMCPAddress(str(exc)) from exc

        error: Exception | None = None
        for address in addresses:
            try:
                return await self._backend.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout, OSError) as exc:
                error = exc
        raise httpcore.ConnectError(str(error)) from error

    async def connect_unix_socket(self, *args, **kwargs):
        raise UnsafeMCPAddress("Unix sockets are not allowed.")

    async def sleep(self, seconds: float) -> None:
        await self._backend.sleep(seconds)


class _ValidatingTransport(httpx.AsyncHTTPTransport):
    def __init__(self, allow_private: bool):
        super().__init__(trust_env=False)
        # Same pool httpx builds, with the validating backend.
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=self._pool._ssl_context,
            max_connections=10,
            max_keepalive_connections=5,
            http1=True,
            http2=False,
            network_backend=_ValidatingNetworkBackend(allow_private),
        )


def allows_private_addresses() -> bool:
    return bool(settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS)


def create_mcp_http_client(headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    """
    An HTTP client for MCP servers that never reaches private or local addresses
    unless the instance allows it, ignores proxy environment variables, and does
    not follow redirects. The MCP transport only follows redirects within the
    server's origin.

    :param headers: Sent with every request, e.g. the server's credential.
    :return: The client, to be used as an async context manager.
    """

    return httpx.AsyncClient(
        transport=_ValidatingTransport(allows_private_addresses()),
        headers=headers,
        timeout=httpx.Timeout(MCP_CONNECT_TIMEOUT, read=MCP_READ_TIMEOUT),
        follow_redirects=False,
        trust_env=False,
    )
