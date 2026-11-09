from channels_redis.core import RedisChannelLayer

from baserow.core.redis import AsyncRetryingConnectionPool, async_redis_pool_options


class RetryingRedisChannelLayer(RedisChannelLayer):
    """
    A Redis channel layer whose pools survive connections the server closed.

    channels-redis builds plain pools, so commands get no retries at all and a
    pooled connection Redis already closed fails the next websocket event. This
    builds an `AsyncRetryingConnectionPool` with the options every asyncio client
    shares instead. Options set on the host entry take precedence over those
    defaults. Sentinel hosts keep channels-redis' own pool.
    """

    def create_pool(self, index):
        host = self.hosts[index]
        if "master_name" in host:
            return super().create_pool(index)

        options = {**async_redis_pool_options(), **host}
        address = options.pop("address", None)
        if address is not None:
            return AsyncRetryingConnectionPool.from_url(address, **options)
        return AsyncRetryingConnectionPool(**options)
