from __future__ import annotations

from typing import Any, Optional

import requests

from .adapter import SSRFSafeAdapter
from .exceptions import InvalidSSRFAddress, SSRFException
from .validator import SSRFValidator

__all__ = [
    "SSRFValidator",
    "SSRFSafeAdapter",
    "SSRFException",
    "InvalidSSRFAddress",
    "ssrf_safe_request",
    "validate_url",
]


class _SSRFSafeClient:
    """
    HTTP client with SSRF protection. Provides convenience methods
    (.get, .post, .request, etc.) that mirror the requests library API
    while validating resolved IP addresses before connecting.
    """

    def _make_request(
        self,
        method: str,
        url: str,
        validator: Optional[SSRFValidator] = None,
        **kwargs: Any,
    ) -> requests.Response:
        if validator is None:
            validator = SSRFValidator()

        with requests.Session() as session:
            # Ignore HTTP_PROXY / HTTPS_PROXY env vars — proxies could
            # bypass SSRF validation by routing to internal addresses.
            session.trust_env = False
            session.mount(
                "http://", SSRFSafeAdapter(validator=validator, is_https=False)
            )
            session.mount(
                "https://", SSRFSafeAdapter(validator=validator, is_https=True)
            )
            return session.request(method, url, **kwargs)

    def request(
        self,
        method: str,
        url: str,
        validator: Optional[SSRFValidator] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Make an HTTP request with SSRF protection.

        :param method: HTTP method (GET, POST, etc.)
        :param url: Target URL.
        :param validator: Optional SSRFValidator instance. If None, a default
            validator with no custom rules is used (blocks all private IPs).
        :param kwargs: Passed through to requests.Session.request().
        :returns: requests.Response
        :raises InvalidSSRFAddress: If the resolved address is blocked.
        """

        return self._make_request(method, url, validator=validator, **kwargs)

    def get(
        self,
        url: str,
        validator: Optional[SSRFValidator] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make a GET request with SSRF protection."""

        kwargs.setdefault("allow_redirects", True)
        return self._make_request("GET", url, validator=validator, **kwargs)

    def post(
        self,
        url: str,
        validator: Optional[SSRFValidator] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make a POST request with SSRF protection."""

        return self._make_request("POST", url, validator=validator, **kwargs)

    def put(
        self,
        url: str,
        validator: Optional[SSRFValidator] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make a PUT request with SSRF protection."""

        return self._make_request("PUT", url, validator=validator, **kwargs)

    def patch(
        self,
        url: str,
        validator: Optional[SSRFValidator] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make a PATCH request with SSRF protection."""

        return self._make_request("PATCH", url, validator=validator, **kwargs)

    def delete(
        self,
        url: str,
        validator: Optional[SSRFValidator] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make a DELETE request with SSRF protection."""

        return self._make_request("DELETE", url, validator=validator, **kwargs)

    def head(
        self,
        url: str,
        validator: Optional[SSRFValidator] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make a HEAD request with SSRF protection."""

        kwargs.setdefault("allow_redirects", False)
        return self._make_request("HEAD", url, validator=validator, **kwargs)

    def options(
        self,
        url: str,
        validator: Optional[SSRFValidator] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Make an OPTIONS request with SSRF protection."""

        kwargs.setdefault("allow_redirects", True)
        return self._make_request("OPTIONS", url, validator=validator, **kwargs)


ssrf_safe_request = _SSRFSafeClient()


def validate_url(
    hostname: str,
    port: int,
    validator: Optional[SSRFValidator] = None,
    timeout: Optional[float] = None,
) -> tuple[str, int]:
    """
    Pre-flight URL validation: resolves the hostname and checks that the
    resulting IP address is allowed, without making an HTTP request.

    Used by webhook URL validation to check addresses at save time.

    :param hostname: Hostname or IP to validate.
    :param port: Port number.
    :param validator: Optional SSRFValidator instance.
    :param timeout: Optional DNS resolution timeout in seconds.
    :returns: Tuple of (ip_string, port) if valid.
    :raises InvalidSSRFAddress: If the resolved address is blocked.
    """

    if validator is None:
        validator = SSRFValidator()

    return validator.validate_address(hostname, port, timeout=timeout)
