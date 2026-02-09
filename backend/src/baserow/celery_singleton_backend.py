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
    ensure that task is eventually run.
    """

    def __init__(self, key: str):
        self.key = key

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

        return cache.set(
            key=self.key,
            value=True,
            timeout=settings.AUTO_INDEX_LOCK_EXPIRY * 2,
        )

    def clear(self) -> bool:
        """
        Clears the flag for the task.
        :return: True if the flag was cleared, False otherwise.
        """

        return cache.delete(key=self.key)
