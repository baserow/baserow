import time
from collections import deque
from collections.abc import Iterable
from functools import wraps
from math import ceil
from uuid import uuid4

from django.conf import settings
from django.core.cache import cache

from django_redis import get_redis_connection
from loguru import logger
from rest_framework.throttling import BaseThrottle, SimpleRateThrottle

from baserow.api.exceptions import ThrottledAPIException
from baserow.core.utils import get_user_remote_ip_address_from_request

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


# Evaluates every configured rate limit and reserves a slot in the same round
# trip. Doing this in one script is what makes the limit hold under a burst:
# with a separate count and insert, parallel requests all observe the same free
# slot before any of them has taken it.
reserve_rate_limit_slot_if_allowed_lua_script = """
local key = KEYS[1]

local timestamp = tonumber(ARGV[1])
local member = ARGV[2]
local largest_period = tonumber(ARGV[3])

redis.call("zremrangebyscore", key, 0, timestamp - largest_period)

-- The first element tells the caller whether the slot was reserved, the rest
-- are the number of calls counted for every rate limit, in the same order.
local result = {1}
local allowed = true

for index = 4, #ARGV, 2 do
  local period = tonumber(ARGV[index])
  local number_of_calls = tonumber(ARGV[index + 1])
  local count = redis.call("zcount", key, timestamp - period, "+inf")

  result[#result + 1] = count

  if count >= number_of_calls then
    allowed = false
  end
end

if allowed then
  redis.call("zadd", key, timestamp, member)
  redis.call("expire", key, largest_period)
else
  result[1] = 0
end

return result
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


class RateLimitThrottle(BaseThrottle):
    """
    Throttles a view based on a configurable list of ``RateLimit`` rules, for
    example 30 calls per minute and 100 calls per hour at the same time. It's
    disabled when no rate limits are configured.

    Every allowed call reserves a slot in a Redis sorted set holding the
    timestamps of the recent calls, and all rate limits are evaluated against
    that same set. Checking and reserving happen in one atomic Lua script, so
    unlike DRF's ``SimpleRateThrottle``, which reads a list from the cache and
    writes it back, the limit also holds when requests come in parallel.

    Subclasses must set ``scope`` and implement ``get_rate_limits`` and
    ``get_ident``. Views that should only count calls that actually did
    something must call ``release`` when they didn't, because the slot is
    reserved before the view runs.
    """

    scope = None
    cache_key_format = "baserow_rate_limit:%(scope)s:%(ident)s"
    _reserve_script = None

    def __init__(self):
        self._wait = None
        self._reserved = None

    @property
    def reserve_script(self):
        # Registering compiles the script once and lets redis-py call it by its
        # hash, falling back to sending the source when redis doesn't know it.
        if RateLimitThrottle._reserve_script is None:
            RateLimitThrottle._reserve_script = self.redis_cli.register_script(
                reserve_rate_limit_slot_if_allowed_lua_script
            )
        return RateLimitThrottle._reserve_script

    @property
    def redis_cli(self):
        return _get_redis_cli()

    def timer(self):
        return time.time()

    def get_rate_limits(self, request) -> Iterable[RateLimit]:
        """
        Returns the rate limits that must be applied to the provided request. An
        empty value disables the throttle.
        """

        raise NotImplementedError(
            "The get_rate_limits method must be implemented by the subclass."
        )

    def get_ident(self, request) -> str | None:
        """
        Returns the identifier of the subject the calls are counted for, for
        example a user id or an IP address, or ``None`` if the request must be
        exempt from the rate limits.
        """

        raise NotImplementedError(
            "The get_ident method must be implemented by the subclass."
        )

    def get_cache_key(self, request) -> str | None:
        ident = self.get_ident(request)

        if ident is None:
            return None

        return self.cache_key_format % {"scope": self.scope, "ident": ident}

    def allow_request(self, request, view) -> bool:
        rate_limits = tuple(self.get_rate_limits(request) or ())

        if not rate_limits or (cache_key := self.get_cache_key(request)) is None:
            return True

        now = self.timer()
        member = str(uuid4())
        largest_period = max(rate.period_in_seconds for rate in rate_limits)

        args = [now, member, largest_period]
        for rate in rate_limits:
            args += [rate.period_in_seconds, rate.number_of_calls]

        reserved, *counts = self.reserve_script(
            keys=[cache_key], args=args, client=self.redis_cli
        )

        if not reserved:
            waits = [
                (self._seconds_until_window_frees_up(cache_key, rate, count, now), rate)
                for rate, count in zip(rate_limits, counts)
                if count >= rate.number_of_calls
            ]
            # Every exceeded rate limit has to accept the call again, so the one
            # that takes the longest determines when it's worth retrying.
            wait, rate = max(waits, key=lambda wait_and_rate: wait_and_rate[0])
            self._deny(request, cache_key, rate, wait)

        self._reserved = (cache_key, member)

        return True

    def release(self):
        """
        Gives the reserved slot back so that the call doesn't count towards the
        rate limits, for example because the view didn't get to do the work that
        the limits are meant to protect. Calling it without a reservation, or
        more than once, does nothing.
        """

        if self._reserved is None:
            return

        cache_key, member = self._reserved
        self._reserved = None
        self.redis_cli.zrem(cache_key, member)

    def _seconds_until_window_frees_up(
        self, cache_key: str, rate: RateLimit, count: int, now: float
    ) -> int:
        """
        Returns how long it takes before the provided rate limit accepts a call
        again, given that ``count`` calls are currently in its window.

        Enough of the oldest calls must leave the window to get back under the
        limit, so with `count` calls and a limit of `n` it's the `count - n + 1`
        oldest call that must expire.

        Only the calls within the window of this rate limit are looked at,
        because the sorted set also holds older calls that are only still
        relevant to a rate limit with a longer period.
        """

        window_start = now - rate.period_in_seconds
        oldest = self.redis_cli.zrangebyscore(
            cache_key,
            window_start,
            "+inf",
            start=max(0, count - rate.number_of_calls),
            num=1,
            withscores=True,
        )

        if not oldest:
            return rate.period_in_seconds

        oldest_timestamp = oldest[0][1]
        return max(1, ceil(oldest_timestamp + rate.period_in_seconds - self.timer()))

    def _deny(self, request, cache_key: str, rate: RateLimit, wait: int):
        logger.warning(
            "Denying {scope} request on path={path} for key={cache_key} for {wait} "
            "seconds. Exceeded limit: {calls} per {period}s",
            scope=self.scope,
            path=request.path,
            cache_key=cache_key,
            wait=wait,
            calls=rate.number_of_calls,
            period=rate.period_in_seconds,
        )
        self._wait = wait
        raise ThrottledAPIException(wait=wait)

    def wait(self):
        return self._wait


class WorkspaceInvitationRateThrottle(RateLimitThrottle):
    """
    Limits how many workspace invitations a single user can send, using the rate
    limits configured in ``BASEROW_WORKSPACE_INVITATION_RATE_LIMITS``.

    Only invitations that were actually created and emailed count, so a request
    failing on for example a permission or validation error doesn't cost the user
    any budget. The view takes care of that by releasing the reserved slot when
    it responds with an error.

    The counter is keyed on the user, not on the workspace, because an abuser can
    create as many workspaces as they like.
    """

    scope = "workspace_invitation"

    def get_rate_limits(self, request):
        return settings.BASEROW_WORKSPACE_INVITATION_RATE_LIMITS

    def get_ident(self, request) -> str | None:
        user = request.user

        if not user.is_authenticated or user.is_staff:
            return None

        return str(user.id)


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
