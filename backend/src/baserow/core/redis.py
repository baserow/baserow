import json
from collections import defaultdict
from typing import Any, Optional

from redis.client import Redis


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
