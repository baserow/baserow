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


class ResponseTooLarge(httpx.ReadError):
    """A response is larger than `INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES`."""


class _LimitedStream(httpx.AsyncByteStream):
    """Stops reading a response once it's larger than the limit."""

    def __init__(
        self, stream: httpx.AsyncByteStream, max_bytes: int, request: httpx.Request
    ):
        self._stream = stream
        self._max_bytes = max_bytes
        self._request = request

    async def __aiter__(self) -> typing.AsyncIterator[bytes]:
        received = 0
        async for chunk in self._stream:
            received += len(chunk)
            if received > self._max_bytes:
                raise ResponseTooLarge(
                    f"The response is larger than {self._max_bytes} bytes.",
                    request=self._request,
                )
            yield chunk

    async def aclose(self) -> None:
        await self._stream.aclose()


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

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        response = await super().handle_async_request(request)
        max_bytes = settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES
        if not max_bytes:
            return response
        # The limit is on the bytes that arrive, so compressed answers, which
        # could unpack into much more, aren't accepted. Every client sends
        # `Accept-Encoding: identity`.
        if response.headers.get("Content-Encoding", "identity") != "identity":
            await response.aclose()
            raise ResponseTooLarge(
                "The server sent a compressed response.", request=request
            )
        response.stream = _LimitedStream(response.stream, max_bytes, request)
        return response


def allows_private_addresses() -> bool:
    return bool(settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS)


def create_mcp_http_client(headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    """
    An HTTP client for MCP servers that never reaches private or local addresses
    unless the instance allows it, ignores proxy environment variables, and does
    not follow redirects. The MCP transport only follows redirects within the
    server's origin. Responses are limited to
    `INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES`, like the HTTP request integration.

    :param headers: Sent with every request, e.g. the server's credential.
    :return: The client, to be used as an async context manager.
    """

    return httpx.AsyncClient(
        transport=_ValidatingTransport(allows_private_addresses()),
        headers={"Accept-Encoding": "identity", **(headers or {})},
        timeout=httpx.Timeout(MCP_CONNECT_TIMEOUT, read=MCP_READ_TIMEOUT),
        follow_redirects=False,
        trust_env=False,
    )
