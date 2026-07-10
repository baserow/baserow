from django.conf import settings
from django.core.cache import cache

from celery_singleton.backends import RedisBackend
from django_redis import get_redis_connection


class RedisBackendForSingleton(RedisBackend):
    def __init__(self, *args, **kwargs):
        """
        Use the existing redis connection instead of creating a new one.
        """

        self.redis = get_redis_connection("default")


# Compare-and-act on the flag in a single round-trip so we never touch a lock a newer
# holder has taken over between a read and the write (TOCTOU). `expire` takes seconds.
_EXTEND_IF_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("expire", KEYS[1], ARGV[2])
end
return 0
"""

_CLEAR_IF_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


class SingletonAutoRescheduleFlag:
    """
    Flag is used to indicate that a task of this type is pending reschedule.

    When the task ends, if this flag is set, it will re-schedule itself to
    ensure that task is eventually run. Also usable as a fenced run lock via
    `acquire`/`extend`/`clear_if`.
    """

    def __init__(self, key: str, timeout: int = settings.AUTO_INDEX_LOCK_EXPIRY * 2):
        self.key = key
        self.timeout = timeout

    def acquire(self, value=True) -> bool:
        """
        Atomically set the flag only if it's not already set. Returns True if
        acquired. Pass a unique token as `value` to fence the lock.
        """

        return bool(cache.add(self.key, value, timeout=self.timeout))

    def extend_if(self, value) -> bool:
        """
        Ownership-aware heartbeat: reset the TTL only if the current value still
        matches our token. Returns False if we no longer hold the lock (expired or
        taken over by another holder), so the caller can stop instead of running
        unprotected.
        """

        return bool(self._eval_if(_EXTEND_IF_SCRIPT, value, self.timeout))

    def clear_if(self, value) -> bool:
        """Delete the flag only if the current value matches the token."""

        return bool(self._eval_if(_CLEAR_IF_SCRIPT, value))

    def _eval_if(self, script, value, *extra_args):
        """
        Run a compare-and-act Lua script keyed on our token. Values are stored via the
        cache, so reuse its key prefix and serializer to match what `acquire` wrote;
        otherwise the raw redis lookup would never find the key or match the token.
        """

        client = cache.client
        redis_key = client.make_key(self.key)
        token = client.encode(value)
        return client.get_client(write=True).eval(
            script, 1, redis_key, token, *extra_args
        )

    def is_set(self) -> bool:
        """
        Checks if the flag is set.

        :return: True if the lock is set, False otherwise.
        """

        return cache.get(key=self.key) or False

    def set(self) -> bool:
        """
        Sets the flag for the task, indicating it needs to be rescheduled.

        :return: True if the flag was set, False if it was already set.
        """

        return cache.set(key=self.key, value=True, timeout=self.timeout)

    def clear(self) -> bool:
        """
        Clears the flag for the task.

        :return: True if the flag was cleared, False otherwise.
        """

        return cache.delete(key=self.key)
