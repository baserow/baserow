from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from requests.adapters import HTTPAdapter
from requests.models import PreparedRequest, Response

from .exceptions import InvalidSSRFAddress

if TYPE_CHECKING:
    from .validator import SSRFValidator


class SSRFSafeAdapter(HTTPAdapter):
    """
    A requests HTTPAdapter that validates resolved IP addresses before
    establishing connections, preventing SSRF attacks.

    Uses the modern `build_connection_pool_key_attributes` hook (requests
    >= 2.32.2) to intercept hostname resolution. The hostname is resolved
    via the SSRFValidator, and if validation passes, the connection target
    is rewritten to the resolved IP. TLS certificate verification is
    preserved by setting assert_hostname / server_hostname to the original
    domain.
    """

    def __init__(
        self,
        validator: SSRFValidator,
        is_https: bool = False,
        **kwargs: Any,
    ) -> None:
        self._validator = validator
        self._is_https = is_https
        super().__init__(**kwargs)

    def build_connection_pool_key_attributes(
        self,
        request: PreparedRequest,
        verify: bool,
        cert: Optional[tuple[str, str]] = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        host_params, pool_kwargs = super().build_connection_pool_key_attributes(
            request, verify, cert
        )

        original_host: str = host_params.get("host", "")
        port: Optional[int] = host_params.get("port")

        # Skip validation for empty hosts (shouldn't happen in practice)
        if not original_host:
            return host_params, pool_kwargs

        # Determine port from the URL if not available from host_params
        if port is None:
            port = 443 if self._is_https else 80

        # Validate and resolve the address
        resolved_ip, _ = self._validator.validate_address(original_host, port)

        # Preserve the original hostname in the Host header
        if request.headers is None:
            from requests.structures import CaseInsensitiveDict

            request.headers = CaseInsensitiveDict()
        else:
            # Copy to avoid mutating shared state
            request.headers = request.headers.copy()

        if "Host" not in request.headers:
            request.headers["Host"] = original_host

        # For HTTPS, ensure TLS certificate validation uses the original
        # hostname, not the resolved IP
        if self._is_https:
            pool_kwargs["assert_hostname"] = original_host
            pool_kwargs["server_hostname"] = original_host

        # Rewrite the connection target to the resolved IP. This prevents
        # TOCTOU races where DNS could resolve to a different address between
        # validation and connection.
        host_params["host"] = resolved_ip

        return host_params, pool_kwargs

    def get_connection(
        self,
        url: str,
        proxies: Optional[dict[str, str]] = None,
    ) -> None:
        raise NotImplementedError(
            "SSRFSafeAdapter requires requests >= 2.32.2 which uses "
            "get_connection_with_tls_context instead of get_connection."
        )

    def proxy_manager_for(
        self,
        proxy: str,
        **proxy_kwargs: Any,
    ) -> None:
        raise NotImplementedError(
            "SSRFSafeAdapter does not support proxies to prevent SSRF bypass."
        )

    def send(
        self,
        request: PreparedRequest,
        stream: bool = False,
        timeout: Optional[float] = None,
        verify: bool = True,
        cert: Optional[tuple[str, str]] = None,
        proxies: Optional[dict[str, str]] = None,
    ) -> Response:
        # Intercept requests with proxies set
        if proxies:
            raise InvalidSSRFAddress(
                message="Proxies are not allowed with SSRF protection enabled."
            )
        return super().send(
            request,
            stream=stream,
            timeout=timeout,
            verify=verify,
            cert=cert,
            proxies=proxies,
        )
