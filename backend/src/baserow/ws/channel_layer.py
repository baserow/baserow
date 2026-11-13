from django.conf import settings

from channels_redis.core import RedisChannelLayer
from channels_redis.serializers import MsgPackSerializer, registry
from compression import zstd

from baserow.core.redis import AsyncRetryingConnectionPool, async_redis_pool_options

COMPRESSED_MSGPACK_SERIALIZER_FORMAT = "compressed_msgpack"
# Below this size the bytes saved don't outweigh the time it takes to compress.
COMPRESSION_MIN_BYTES = 16 * 1024
# Every Zstandard frame starts with these bytes. A channel layer message is a
# dict, which MessagePack never starts with this byte, so the two can't be confused.
ZSTD_FRAME_MAGIC = b"\x28\xb5\x2f\xfd"


class CompressedMsgPackSerializer(MsgPackSerializer):
    """
    MessagePack, compressed with Zstandard when the message is large.

    The channel layer writes a copy of a group message to Redis for every ASGI
    process that has a member in the group, so a large message costs many times
    its size in Redis memory, persistence and replication.

    Compressed messages are always understood. They are only written when
    `REALTIME_COMPRESSION_ENABLED` is on, because processes running a version
    without this serializer can't read them.
    """

    def as_bytes(self, message, *args, **kwargs):
        data = MsgPackSerializer.as_bytes(message, *args, **kwargs)
        if settings.REALTIME_COMPRESSION_ENABLED and len(data) >= COMPRESSION_MIN_BYTES:
            print('compress')
            return zstd.compress(data)
        return data

    def from_bytes(self, message, *args, **kwargs):
        if message.startswith(ZSTD_FRAME_MAGIC):
            message = zstd.decompress(message)
        return MsgPackSerializer.from_bytes(message, *args, **kwargs)


registry.register_serializer(
    COMPRESSED_MSGPACK_SERIALIZER_FORMAT, CompressedMsgPackSerializer
)


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
