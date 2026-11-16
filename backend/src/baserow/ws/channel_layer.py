import asyncio
import time
from collections import defaultdict

from django.conf import settings

from channels_redis.core import RedisChannelLayer
from channels_redis.serializers import MsgPackSerializer, registry
from compression import zstd
from loguru import logger

from baserow.core.redis import AsyncRetryingConnectionPool, async_redis_pool_options
from baserow.core.utils import grouper

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
            return zstd.compress(data)
        return data

    def from_bytes(self, message, *args, **kwargs):
        if message.startswith(ZSTD_FRAME_MAGIC):
            message = zstd.decompress(message)
        return MsgPackSerializer.from_bytes(message, *args, **kwargs)


registry.register_serializer(
    COMPRESSED_MSGPACK_SERIALIZER_FORMAT, CompressedMsgPackSerializer
)

# More than once, so that a renewal can fail, during a Redis failover for example,
# without the connection dropping out of its groups. If more of them fail, the first
# one that succeeds adds the connection to its groups again.
GROUP_RENEWALS_PER_EXPIRY = 3
# A channel nobody receives on can still come back, when its consumer was busy for
# a long time for example, and then needs its memberships again. It can't be
# remembered forever, because a consumer that crashed never removes its channel.
FORGET_CHANNEL_AFTER_GROUP_EXPIRIES = 4
GROUP_RENEWAL_BATCH_SIZE = 500


class RetryingRedisChannelLayer(RedisChannelLayer):
    """
    A Redis channel layer whose pools survive connections the server closed.

    channels-redis builds plain pools, so commands get no retries at all and a
    pooled connection Redis already closed fails the next websocket event. This
    builds an `AsyncRetryingConnectionPool` with the options every asyncio client
    shares instead. Options set on the host entry take precedence over those
    defaults. Sentinel hosts keep channels-redis' own pool.

    A process that is killed or restarted never removes its channels from their
    groups, and every group message is copied to them until the group expiry
    passes. Renewing the memberships of live channels lets that expiry be minutes
    instead of a day, without live connections dropping out of their groups.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._group_memberships: dict[str, set[str]] = {}
        self._active_receives: dict[str, int] = {}
        self._idle_since: dict[str, float] = {}
        self._group_renewal_task: asyncio.Task | None = None
        self._group_renewal_lock = asyncio.Lock()

    @property
    def group_renewal_interval(self) -> float:
        return self.group_expiry / GROUP_RENEWALS_PER_EXPIRY

    async def group_add(self, group, channel):
        await super().group_add(group, channel)
        self._group_memberships.setdefault(channel, set()).add(group)
        if channel not in self._active_receives:
            self._idle_since.setdefault(channel, time.monotonic())
        self._ensure_group_renewal_task()

    async def group_discard(self, group, channel):
        groups = self._group_memberships.get(channel)
        if groups is not None:
            groups.discard(group)
            if not groups:
                self._forget_channel(channel)
        renewing = self._group_renewal_lock.locked()
        await super().group_discard(group, channel)
        if renewing:
            # The renewal that is being written to Redis right now may add the
            # channel to the group again after it was removed here. The channel
            # would then keep receiving the messages of a group it left, for
            # example after the user lost access to a table.
            async with self._group_renewal_lock:
                pass
            if group not in self._group_memberships.get(channel, ()):
                await super().group_discard(group, channel)

    async def receive(self, channel):
        # A consumer waits on its channel for as long as it lives, which is how a
        # channel that is still in use is told apart from one left behind.
        self._active_receives[channel] = self._active_receives.get(channel, 0) + 1
        self._idle_since.pop(channel, None)
        try:
            return await super().receive(channel)
        finally:
            self._active_receives[channel] -= 1
            if not self._active_receives[channel]:
                del self._active_receives[channel]
                if channel in self._group_memberships:
                    self._idle_since[channel] = time.monotonic()

    def _forget_channel(self, channel):
        self._group_memberships.pop(channel, None)
        self._idle_since.pop(channel, None)

    def _ensure_group_renewal_task(self):
        loop = asyncio.get_running_loop()
        task = self._group_renewal_task
        if task is None or task.done() or task.get_loop() is not loop:
            self._group_renewal_task = loop.create_task(
                self._renew_group_memberships_periodically()
            )

    async def _renew_group_memberships_periodically(self):
        while True:
            await asyncio.sleep(self.group_renewal_interval)
            try:
                await self.renew_group_memberships()
            except Exception:
                # The next round adds the memberships again, also the ones that
                # expired in the meantime.
                logger.exception("Failed to renew the channel group memberships.")

    async def renew_group_memberships(self):
        # The expired members are removed here as well, because the channel layer
        # itself only removes them when it sends to the group. They would otherwise
        # pile up in groups that rarely get a message.
        idle_before = time.monotonic() - self.group_renewal_interval
        forget_before = (
            time.monotonic() - self.group_expiry * FORGET_CHANNEL_AFTER_GROUP_EXPIRIES
        )
        now = time.time()
        channels_per_group = defaultdict(dict)
        for channel, groups in list(self._group_memberships.items()):
            idle_since = self._idle_since.get(channel)
            if idle_since is not None and idle_since <= forget_before:
                self._forget_channel(channel)
            elif idle_since is None or idle_since > idle_before:
                for group in groups:
                    channels_per_group[group][channel] = now

        for batch in grouper(GROUP_RENEWAL_BATCH_SIZE, channels_per_group.items()):
            # Lets `group_discard` know that a batch is being written, see there.
            async with self._group_renewal_lock:
                pipelines = {}
                for group, channels in batch:
                    channels = {
                        channel: score
                        for channel, score in channels.items()
                        if group in self._group_memberships.get(channel, ())
                    }
                    if not channels:
                        continue
                    index = self.consistent_hash(group)
                    if index not in pipelines:
                        pipelines[index] = self.connection(index).pipeline(
                            transaction=False
                        )
                    group_key = self._group_key(group)
                    pipelines[index].zremrangebyscore(
                        group_key, min=0, max=int(now) - self.group_expiry
                    )
                    pipelines[index].zadd(group_key, channels)
                    pipelines[index].expire(group_key, self.group_expiry)
                for pipeline in pipelines.values():
                    await pipeline.execute()

    def create_pool(self, index):
        host = self.hosts[index]
        if "master_name" in host:
            return super().create_pool(index)

        options = {**async_redis_pool_options(), **host}
        address = options.pop("address", None)
        if address is not None:
            return AsyncRetryingConnectionPool.from_url(address, **options)
        return AsyncRetryingConnectionPool(**options)
