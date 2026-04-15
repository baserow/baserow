"""
Redis blacklist for throttled tokens and IPs.

When the ``ConcurrentUserRequestsThrottle`` denies a request, the bearer
token's SHA-256 hash (or the client IP) is written here.  The
``ThrottleBlacklistMiddleware`` checks this blacklist *before* authentication
so that repeat offenders are rejected with zero DB or DRF overhead.
"""

import hashlib
import math

from django.core.cache import cache

_TOKEN_PREFIX = "throttle_bl:"
_IP_PREFIX = "throttle_ip_bl:"


def _token_key(raw_token: str) -> str:
    return _TOKEN_PREFIX + hashlib.sha256(raw_token.encode()).hexdigest()


def _ip_key(ip: str) -> str:
    return _IP_PREFIX + ip


def blacklist_token(raw_token: str, wait_seconds: float) -> None:
    """Add a token hash to the throttle blacklist with the given TTL."""

    ttl = max(1, math.ceil(wait_seconds))
    cache.set(_token_key(raw_token), ttl, timeout=ttl)


def blacklist_ip(ip: str, wait_seconds: float) -> None:
    """Add an IP to the throttle blacklist with the given TTL."""

    ttl = max(1, math.ceil(wait_seconds))
    cache.set(_ip_key(ip), ttl, timeout=ttl)


def is_token_blacklisted(raw_token: str) -> int | None:
    """
    Return the original wait time (seconds) if blacklisted, else ``None``.

    The value is the TTL set at blacklist time — it does not decrease as the
    key ages.  It is used as a ``Retry-After`` hint, not an exact countdown.
    """

    return cache.get(_token_key(raw_token))


def is_ip_blacklisted(ip: str) -> int | None:
    """
    Return the original wait time (seconds) if blacklisted, else ``None``.
    """

    return cache.get(_ip_key(ip))
