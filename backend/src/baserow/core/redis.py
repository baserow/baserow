import json
from collections import defaultdict
from typing import Any, Optional

from redis.asyncio import ConnectionPool as AsyncConnectionPool
from redis.asyncio.retry import Retry as AsyncRetry
from redis.backoff import EqualJitterBackoff
from redis.client import Redis
from redis.connection import ConnectionPool
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ReadOnlyError as RedisReadOnlyError

# redis-py 8 defaults to RESP3, which turns on maintenance notifications. While
# they're on, redis-py 8.1 hands out pooled asyncio connections without checking
# whether the server already closed them (an idle timeout, an HAProxy restart, a
# failover), so the next command fails with "Connection closed by server". RESP2
# restores the check. Fixed upstream in redis-py 8.2.0, after which this can go.
ASYNC_REDIS_PROTOCOL = 2


def async_redis_retry(*errors: type[Exception]) -> AsyncRetry:
    """
    The asyncio counterpart of the retries the Django cache uses: 3 retries
    waiting 2.5 to 5 seconds in total, enough to bridge a Redis restart or
    Sentinel failover without stalling callers long while Redis is down.

    :param errors: The exceptions that may be retried.
    :return: A retry policy for an asyncio pool or connection.
    """

    return AsyncRetry(EqualJitterBackoff(base=0.5, cap=2), 3, supported_errors=errors)


def async_redis_pool_options() -> dict[str, Any]:
    """
    Options for an `AsyncRetryingConnectionPool`, shared by the asyncio clients.

    Taking a connection from the pool is retried on connection errors, which is
    safe because no command has been sent yet. Commands are only retried when
    Redis rejected them as read-only, which happens for a moment when HAProxy
    still routes to a primary that Sentinel just demoted. A connection that drops
    after a command was sent leaves it unknown whether Redis already ran it, so
    those aren't retried.

    :return: Keyword arguments for `AsyncRetryingConnectionPool`.
    """

    return {
        "protocol": ASYNC_REDIS_PROTOCOL,
        "checkout_retry": async_redis_retry(RedisConnectionError),
        "retry": async_redis_retry(RedisReadOnlyError),
    }


class AsyncRetryingConnectionPool(AsyncConnectionPool):
    """
    The asyncio counterpart of `RetryingConnectionPool`: retries taking a
    connection from the pool, which is where a dropped connection reconnects.
    """

    def __init__(self, *args, checkout_retry: AsyncRetry | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.checkout_retry = checkout_retry

    async def get_connection(self, *args, **kwargs):
        get_connection = super().get_connection
        if self.checkout_retry is None:
            return await get_connection(*args, **kwargs)

        async def ignore_failure(error):
            pass

        return await self.checkout_retry.call_with_retry(
            lambda: get_connection(*args, **kwargs), ignore_failure
        )


class RetryingConnectionPool(ConnectionPool):
    """
    redis-py only retries commands, not taking a connection from the pool, which is
    where a dropped connection reconnects. Without this, every call fails right away
    during a Redis restart or failover instead of waiting for it.

    The separate `checkout_retry` is safe for connection errors, because no command
    has been sent yet. A command's own retry can't be: a connection that drops
    before the reply arrives leaves it unknown whether Redis already ran it.
    """

    def __init__(self, *args, checkout_retry=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.checkout_retry = checkout_retry

    def get_connection(self, *args, **kwargs):
        get_connection = super().get_connection
        if self.checkout_retry is None:
            return get_connection(*args, **kwargs)
        return self.checkout_retry.call_with_retry(
            lambda: get_connection(*args, **kwargs), lambda error: None
        )


class RedisQueue:
    """
    This class can be used to enqueue objects in a race condition safe way.
    """

    def __init__(
        self, queue_key: str, redis_connection: Redis, max_length: Optional[int] = None
    ):
        """
        :param queue_key: The unique queue key that's used as key in Redis.
        :param redis_connection: The Redis connection object that must be used to
            read and write.
        :param max_length: The maximum length of the queue. If exceeded then the
            objects won't be enqueued.
        """

        self.queue_key = queue_key
        self.redis_connection = redis_connection
        self.max_length = max_length

    def enqueue_task(self, task_object: Any) -> bool:
        """
        Adds a new task to the queue.

        :param task_object: The object that must be added to the queue.
        :return: Indicates whether the object was added to the queue. If `False`,
            then it's because the queue `max_length` has been exceeded.
        """

        redis_connection = self.redis_connection
        task_data = json.dumps(task_object)

        if self.max_length is None:
            redis_connection.rpush(self.queue_key, task_data)
            return True
        else:
            # The Lua script ensures that the entire operation (counting and adding) is
            # treated as a single atomic unit. This eliminates any possibility of race
            # conditions during this operation.
            lua_script = """
            local queue_key = KEYS[1]
            local max_length = tonumber(ARGV[1])
            local task_data = ARGV[2]

            -- Get the current length of the list
            local current_length = redis.call("LLEN", queue_key)

            -- Check if the length exceeds the maximum allowed
            if current_length < max_length then
                redis.call("RPUSH", queue_key, task_data)
                return 1  -- Success
            else
                return 0  -- Queue is full
            end
            """

            # Load and execute the Lua script
            lua_script_sha = redis_connection.script_load(lua_script)
            result = redis_connection.evalsha(
                lua_script_sha,
                1,  # Number of keys
                self.queue_key,
                self.max_length,
                task_data,
            )

            return result != 0

    def get_and_pop_next(self) -> Any:
        """
        Returns the first object from the queue.

        :return: The first object from the queue.
        """

        # The Lua script ensures that the entire operation (fetching and removing the
        # first item in the queue) is treated as a single atomic unit. This
        # eliminates any possibility of race conditions during this operation.
        lua_script = """
        local key = KEYS[1]
        local task = redis.call("lpop", key)
        if not task then
            return nil
        end
        return task
        """
        result = self.redis_connection.eval(lua_script, 1, self.queue_key)
        return json.loads(result) if result else None

    def clear(self):
        """
        Clears all objects from the queue.
        """

        self.redis_connection.delete(self.queue_key)


class WebhookRedisQueue(RedisQueue):
    queues = defaultdict(list)

    def enqueue_task(self, task_object):
        self.queues[self.queue_key].append(task_object)
        return True

    def get_and_pop_next(self):
        try:
            return self.queues[self.queue_key].pop(0)
        except IndexError:
            return None

    def clear(self):
        self.queues[self.queue_key] = []
