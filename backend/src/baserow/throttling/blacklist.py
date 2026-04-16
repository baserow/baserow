"""
Redis blacklist for throttled tokens and IPs.

When the ``ConcurrentUserRequestsThrottle`` denies a request, the bearer
token's SHA-256 hash (or the client IP) is written here.  The
``ThrottleBlacklistMiddleware`` checks this blacklist *before* authentication
so that repeat offenders are rejected with zero DB or DRF overhead.
"""

import hashlib

from django.conf import settings
from django.core.cache import cache

_TOKEN_PREFIX = "throttle_bl:"
_IP_PREFIX = "throttle_ip_bl:"


def _token_key(raw_token: str) -> str:
    return _TOKEN_PREFIX + hashlib.sha256(raw_token.encode()).hexdigest()


def _ip_key(ip: str) -> str:
    return _IP_PREFIX + ip


def get_blacklist_ttl() -> int:
    return max(1, settings.BASEROW_THROTTLE_BLACKLIST_TTL)


def blacklist_token(raw_token: str, ttl: int | None = None) -> None:
    ttl = ttl or get_blacklist_ttl()
    cache.set(_token_key(raw_token), ttl, timeout=ttl)


def blacklist_ip(ip: str, ttl: int | None = None) -> None:
    ttl = ttl or get_blacklist_ttl()
    cache.set(_ip_key(ip), ttl, timeout=ttl)


def is_token_blacklisted(raw_token: str) -> int | None:
    """Return the blacklist TTL if blacklisted, else ``None``.

    The stored value is the TTL at blacklist time (it does not tick down).
    Used as a ``Retry-After`` hint, not an exact countdown.
    """

    return cache.get(_token_key(raw_token))


def is_ip_blacklisted(ip: str) -> int | None:
    """Return the blacklist TTL if blacklisted, else ``None``.

    The stored value is the TTL at blacklist time (it does not tick down).
    Used as a ``Retry-After`` hint, not an exact countdown.
    """

    return cache.get(_ip_key(ip))
