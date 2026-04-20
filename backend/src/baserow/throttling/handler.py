import time
from collections import deque
from functools import wraps
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache

from django_redis import get_redis_connection
from loguru import logger
from rest_framework.throttling import SimpleRateThrottle

from baserow.api.exceptions import ThrottledAPIException
from baserow.api.sessions import get_user_remote_ip_address_from_request

from .blacklist import blacklist_ip, blacklist_token
from .exceptions import RateLimitExceededException
from .types import RateLimit
from .utils import get_auth_token

BASEROW_CONCURRENCY_THROTTLE_REQUEST_ID = "baserow_concurrency_throttle_request_id"

# Slightly modified version of
# https://gist.github.com/ptarjan/e38f45f2dfe601419ca3af937fff574d
incr_concurrent_requests_count_if_allowed_lua_script = """
local key = KEYS[1]

local max_concurrent_requests = tonumber(ARGV[1])
local timestamp = tonumber(ARGV[2])
local request_id = ARGV[3]
local timeout = tonumber(ARGV[4])
local old_request_cutoff = timestamp - timeout

local count = redis.call("zcard", key)
local allowed = count < max_concurrent_requests

if not allowed then
  -- If we failed then try to expire any old requests that might still be running and try again
  -- We don't always call "zremrangebyscore" to speed up the normal path that doesn't get throttled.
  local num_removed = redis.call("zremrangebyscore", key, 0, old_request_cutoff)
  count = count - num_removed
  allowed = count < max_concurrent_requests
end

if allowed then
  redis.call("zadd", key, timestamp, request_id)
end

return { allowed, count }
"""


def _get_redis_cli():
    return get_redis_connection("default")


class ConcurrentUserRequestsThrottle(SimpleRateThrottle):
    """
    Limits the number of concurrent requests made by a given user or IP address. When
    the limit is exceeded and the blacklist is enabled, the token or IP is blacklisted
    for a short time to prevent further abuse and reduce load on the system.  See
    ``ThrottleBlacklistMiddleware`` and ``baserow.throttling.blacklist``.
    """

    scope = "concurrent_user_requests"
    redis_cli = None

    def __new__(cls, *args, **kwargs):
        if cls.redis_cli is None:
            cls._init_redis_cli()
        return super().__new__(cls, *args, **kwargs)

    @classmethod
    def _init_redis_cli(cls):
        cls.redis_cli = _get_redis_cli()
        cls.is_allowed = cls.redis_cli.register_script(
            incr_concurrent_requests_count_if_allowed_lua_script
        )

    @classmethod
    def _get_ip(cls, request) -> str:
        return get_user_remote_ip_address_from_request(request)

    @classmethod
    def _debug(cls, request, log_msg, request_id=None, **kwargs):
        logger.debug(
            "{{path={path},user_id={user_id},req_id={request_id}}} " + log_msg,
            path=request.path,
            user_id=request.user.id if request.user.is_authenticated else None,
            request_id=str(request_id),
            **kwargs,
        )

    def parse_rate(self, rate):
        duration = settings.BASEROW_CONCURRENT_USER_REQUESTS_THROTTLE_TIMEOUT
        return int(rate), duration

    @classmethod
    def get_cache_key(cls, request, view=None) -> str | None:
        """
        Return a unique cache key for the given request, or ``None`` if the request
        should be exempt from throttling:

        - Staff users are always exempt.

        - if the user is authenticated, the key is base on the user ID, so all tokens
          for the same user share the same concurrency limit.

        - If the user is anonymous and IP-based throttling is enabled, the key is based
          on the client IP.

        - If the user is anonymous and IP-based throttling is disabled, ``None`` is
          returned to skip throttling.
        """

        user = request.user

        if user.is_authenticated:
            if user.is_staff:  # Don't throttle staff users
                return None

            ident = str(user.id)
        elif settings.BASEROW_THROTTLE_IP_ENABLED:
            ident = cls._get_ip(request)
        else:
            return None

        return cls.cache_format % {"scope": cls.scope, "ident": ident}

    def allow_request(self, request, view):
        profile = getattr(request.user, "profile", None)
        limit = (
            profile and getattr(profile, "concurrency_limit", None) or self.num_requests
        )

        if limit <= 0 or (cache_key := self.get_cache_key(request)) is None:
            self._debug(request, "ALLOWING: throttling skipped")
            return True

        self.cache_key = cache_key
        self.timestamp = timestamp = self.timer()
        request_id = str(uuid4())

        args = [limit, timestamp, request_id, self.duration]
        allowed, count = self.is_allowed([cache_key], args)

        if not allowed:
            self._raise_deny_exc(request, request_id, count, limit)

        return self._allow(request, request_id, count, limit)

    def _allow(self, request, request_id, count, limit):
        django_request = request._request
        # Needed to remove request from sorted set in on_request_processed when done.
        setattr(django_request, BASEROW_CONCURRENCY_THROTTLE_REQUEST_ID, request_id)
        self._debug(
            request,
            "ALLOWING: as count={count} < limit={limit}",
            request_id=request_id,
            count=count,
            limit=limit,
        )
        return True

    def _raise_deny_exc(self, request, request_id, count, limit):
        """
        Raise ThrottledAPIException to reject the request. When the blacklist
        is enabled (BASEROW_THROTTLE_BLACKLIST_TTL_SECONDS > 0) the caller is
        also blacklisted for that cooldown, and the cooldown is surfaced as
        the Retry-After hint; otherwise no Retry-After is emitted since a
        concurrency slot may free up at any moment.
        """

        cooldown = settings.BASEROW_THROTTLE_BLACKLIST_TTL_SECONDS
        if cooldown > 0:
            self._blacklist(request, ttl=cooldown)
        else:
            cooldown = None

        self._wait = cooldown
        self._debug(
            request,
            "DENYING: as count={count} >= limit={limit}. Cooldown {wait} secs",
            request_id=request_id,
            count=count,
            limit=limit,
            wait=cooldown,
        )

        raise ThrottledAPIException(wait=cooldown)

    @classmethod
    def _blacklist(cls, request, ttl: int | None = None) -> None:
        token = get_auth_token(request)
        if token:
            blacklist_token(token, ttl=ttl)
        else:
            ip = cls._get_ip(request)
            blacklist_ip(ip, ttl=ttl)

    @classmethod
    def on_request_processed(cls, request):
        request_id = getattr(request, BASEROW_CONCURRENCY_THROTTLE_REQUEST_ID, None)
        if request_id and (cache_key := cls.get_cache_key(request)):
            cls._debug(
                request, "UNTRACKING: request has finished", request_id=request_id
            )
            cls.redis_cli.zrem(cache_key, request_id)

    def wait(self):
        return self._wait


def rate_limit(rate: RateLimit, key: str, raise_exception: bool = True):
    """
    A general purpose throttling function decorator.

    Currently the implementation is not suitable for highly concurrent access
    as multiple callers can overwrite cached timestamps.

    :param rate: The number of allowed calls over specified period.
    :param key: The key parametrizes the same function calls that should be
        throttled.
    :param raise_exception: Whether exception should be raised when the rate
        limit is exceeded.
    :raises RateLimitExceededException: Raised when the rate
        limit is exceeded.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{key}"
            timestamps = cache.get(cache_key, deque())
            current_time = time.time()

            # Remove timestamps outside the current window
            while timestamps and timestamps[0] <= current_time - rate.period_in_seconds:
                timestamps.popleft()

            if len(timestamps) >= rate.number_of_calls:
                if raise_exception:
                    raise RateLimitExceededException(
                        f"Rate limit exceeded for {func.__name__}"
                    )
                else:
                    return None

            timestamps.append(current_time)
            cache.set(cache_key, timestamps, timeout=rate.period_in_seconds)

            return func(*args, **kwargs)

        return wrapper

    return decorator
