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

    def extend(self) -> bool:
        """
        Reset the TTL without changing the value (heartbeat). Returns False if
        the key is gone, so a straggler can't recreate it.
        """

        return bool(cache.touch(self.key, self.timeout))

    def clear_if(self, value) -> bool:
        """Delete the flag only if the current value matches the token."""

        if cache.get(self.key) == value:
            return cache.delete(self.key)
        return False

    def is_set(self) -> bool:
        return cache.get(key=self.key) or False

    def set(self) -> bool:
        return cache.set(key=self.key, value=True, timeout=self.timeout)

    def clear(self) -> bool:
        return cache.delete(key=self.key)
