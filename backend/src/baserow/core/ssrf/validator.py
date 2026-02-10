from __future__ import annotations

import re
import socket
from ipaddress import (
    IPv4Address,
    IPv4Network,
    IPv6Address,
    IPv6Network,
    ip_address,
    ip_network,
)
from typing import Optional, Union

from .exceptions import InvalidSSRFAddress

IPAddress = Union[IPv4Address, IPv6Address]
IPNetwork = Union[IPv4Network, IPv6Network]

# IP ranges that Python's is_private/is_global miss on some versions.
# These are explicitly dangerous ranges that should always be blocked.
_EXTRA_DENIED_NETWORKS: list[IPNetwork] = [
    ip_network("192.88.99.0/24"),  # 6to4 relay anycast (RFC 7526, deprecated)
    ip_network("100.64.0.0/10"),  # CGNAT shared address space (RFC 6598)
]


class SSRFValidator:
    """
    Validates resolved IP addresses and hostnames against configurable rules
    to prevent Server-Side Request Forgery (SSRF) attacks.

    By default, all private, reserved, loopback, link-local, and non-globally-
    routable IP addresses are blocked. Administrators can extend this with
    custom IP blacklists/whitelists and hostname regex patterns.
    """

    def __init__(
        self,
        ip_blacklist: Optional[list[IPNetwork]] = None,
        ip_whitelist: Optional[list[IPNetwork]] = None,
        hostname_blacklist: Optional[list[re.Pattern]] = None,
    ) -> None:
        self.ip_blacklist: list[IPNetwork] = ip_blacklist or []
        self.ip_whitelist: list[IPNetwork] = ip_whitelist or []
        self.hostname_blacklist: list[re.Pattern] = hostname_blacklist or []

    def _normalize_ip(self, ip: IPAddress) -> IPAddress:
        """Unwrap IPv4-mapped IPv6 addresses to their inner IPv4 address."""

        if isinstance(ip, IPv6Address):
            mapped = ip.ipv4_mapped
            if mapped is not None:
                return mapped
        return ip

    def is_ip_allowed(self, ip: IPAddress) -> bool:
        """
        Check whether an IP address is allowed.

        Order of checks:
        1. User whitelist (explicit allow — takes precedence)
        2. User blacklist (explicit deny)
        3. Built-in checks (private, non-global, extra denied ranges)
        """

        ip = self._normalize_ip(ip)

        # 1. Explicit whitelist takes precedence
        for network in self.ip_whitelist:
            if ip in network:
                return True

        # 2. Explicit blacklist
        for network in self.ip_blacklist:
            if ip in network:
                return False

        # 3. Reject private addresses (loopback, link-local, RFC1918, multicast,
        #    reserved, unspecified, etc.)
        if ip.is_private:
            return False

        # 4. Reject non-globally-routable addresses. This catches ranges that
        #    is_private misses on newer Python versions (e.g., CGNAT on 3.13+).
        if not ip.is_global:
            return False

        # 5. Reject known-dangerous ranges that is_private/is_global miss on
        #    some Python versions (e.g., 6to4 relay, CGNAT on Python 3.11).
        for network in _EXTRA_DENIED_NETWORKS:
            if ip in network:
                return False

        return True

    def is_hostname_allowed(self, hostname: str) -> bool:
        """
        Check whether a hostname is allowed against regex blacklist patterns.
        Patterns are matched from the start of the hostname (re.match behavior).
        Returns True if no patterns match (allowed), False if any match (blocked).
        """

        if not self.hostname_blacklist:
            return True

        # Normalize the hostname to lowercase for consistent matching
        try:
            normalized = hostname.lower().encode("idna").decode("ascii")
        except (UnicodeError, UnicodeDecodeError):
            normalized = hostname.lower()

        # Strip trailing dot for consistent matching
        normalized = normalized.rstrip(".")

        for pattern in self.hostname_blacklist:
            if pattern.match(normalized):
                return False

        return True

    def validate_address(
        self,
        hostname: str,
        port: int,
    ) -> tuple[str, int]:
        """
        Resolve a hostname and validate the resulting IP address(es).

        Returns the first allowed (ip_string, port) tuple.
        Raises InvalidSSRFAddress if no resolved address passes validation.
        """

        # Check hostname against regex blacklist first
        if not self.is_hostname_allowed(hostname):
            raise InvalidSSRFAddress(
                address=hostname,
                message=f"Hostname {hostname!r} is blocked by blacklist",
            )

        try:
            results = socket.getaddrinfo(hostname, port, 0, socket.SOCK_STREAM)
        except socket.gaierror as e:
            raise InvalidSSRFAddress(
                address=hostname,
                message=f"Could not resolve hostname {hostname!r}: {e}",
            ) from e

        if not results:
            raise InvalidSSRFAddress(
                address=hostname,
                message=f"No addresses found for hostname {hostname!r}",
            )

        last_error: Optional[str] = None
        for family, socktype, proto, canonname, sockaddr in results:
            ip_str: str = sockaddr[0]
            try:
                ip = ip_address(ip_str)
            except ValueError:
                continue

            if self.is_ip_allowed(ip):
                return ip_str, port

            last_error = ip_str

        raise InvalidSSRFAddress(
            address=last_error or hostname,
            message=(
                f"All resolved addresses for {hostname!r} were blocked "
                f"by SSRF protection"
            ),
        )
