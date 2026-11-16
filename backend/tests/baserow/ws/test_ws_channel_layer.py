import asyncio
import time
from contextlib import asynccontextmanager
from unittest.mock import patch

from django.test.utils import override_settings

import msgpack
import pytest
from channels_redis.core import RedisChannelLayer

from baserow.ws.channel_layer import (
    COMPRESSED_MSGPACK_SERIALIZER_FORMAT,
    ZSTD_FRAME_MAGIC,
    CompressedMsgPackSerializer,
    RetryingRedisChannelLayer,
)

LARGE_MESSAGE = {
    "type": "broadcast_to_group",
    "payload": {
        "type": "rows_updated",
        "rows": [
            {"id": i, "field_1": f"Row {i}", "field_2": "text"} for i in range(2000)
        ],
    },
}
SMALL_MESSAGE = {"type": "broadcast_to_group", "payload": {"type": "row_updated"}}


@override_settings(REALTIME_COMPRESSION_ENABLED=True)
def test_large_messages_are_compressed_when_enabled():
    serializer = CompressedMsgPackSerializer()

    serialized = serializer.serialize(LARGE_MESSAGE)

    assert serialized.startswith(ZSTD_FRAME_MAGIC)
    assert len(serialized) < len(msgpack.packb(LARGE_MESSAGE)) / 2
    assert serializer.deserialize(serialized) == LARGE_MESSAGE


@override_settings(REALTIME_COMPRESSION_ENABLED=True)
def test_small_messages_are_not_compressed():
    serializer = CompressedMsgPackSerializer()

    serialized = serializer.serialize(SMALL_MESSAGE)

    assert serialized == msgpack.packb(SMALL_MESSAGE)
    assert serializer.deserialize(serialized) == SMALL_MESSAGE


@override_settings(REALTIME_COMPRESSION_ENABLED=False)
def test_messages_are_not_compressed_when_disabled():
    serializer = CompressedMsgPackSerializer()

    assert serializer.serialize(LARGE_MESSAGE) == msgpack.packb(LARGE_MESSAGE)


def test_compressed_messages_are_read_when_disabled():
    serializer = CompressedMsgPackSerializer()
    with override_settings(REALTIME_COMPRESSION_ENABLED=True):
        serialized = serializer.serialize(LARGE_MESSAGE)

    with override_settings(REALTIME_COMPRESSION_ENABLED=False):
        assert serializer.deserialize(serialized) == LARGE_MESSAGE


@override_settings(REALTIME_COMPRESSION_ENABLED=True)
def test_channel_layer_compresses_with_the_configured_serializer():
    layer = RetryingRedisChannelLayer(
        hosts=[{"address": "redis://redis:6379/0"}],
        serializer_format=COMPRESSED_MSGPACK_SERIALIZER_FORMAT,
    )

    serialized = layer.serialize(LARGE_MESSAGE)

    # The channel layer puts a random prefix in front of every message.
    assert serialized[layer._serializer.random_prefix_length :].startswith(
        ZSTD_FRAME_MAGIC
    )
    assert layer.deserialize(serialized) == LARGE_MESSAGE


CHANNEL = "specific.process!connection"
GROUP_KEY = "asgi:group:table-1"


@pytest.fixture
def make_layer():
    # Nothing else stops the renewal task before the event loop of the test closes.

    layers = []

    def make(**kwargs):
        layers.append(RetryingRedisChannelLayer(**kwargs))
        return layers[-1]

    yield make
    for layer in layers:
        if layer._group_renewal_task is not None:
            layer._group_renewal_task.cancel()


@asynccontextmanager
async def receiving(layer, channel):
    async def wait_forever(self, channel):
        await asyncio.Event().wait()

    with patch.object(RedisChannelLayer, "receive", wait_forever):
        task = asyncio.ensure_future(layer.receive(channel))
        await asyncio.sleep(0)
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_groups_of_a_channel_being_received_on_are_renewed(
    channel_layer_redis, make_layer
):
    layer = make_layer(group_expiry=900)
    await layer.group_add("table-1", CHANNEL)
    now = time.time()
    # As if the channel joined ten minutes ago, next to one of a process that died
    # more than the group expiry ago.
    channel_layer_redis.zadd(
        GROUP_KEY, {CHANNEL: now - 600, "specific.dead!connection": now - 1000}
    )
    channel_layer_redis.expire(GROUP_KEY, 300)

    async with receiving(layer, CHANNEL):
        await layer.renew_group_memberships()

    assert channel_layer_redis.zrange(GROUP_KEY, 0, -1) == [CHANNEL.encode()]
    assert channel_layer_redis.zscore(GROUP_KEY, CHANNEL) >= now
    assert channel_layer_redis.ttl(GROUP_KEY) > 800


@pytest.mark.asyncio
async def test_groups_of_an_abandoned_channel_are_not_renewed(
    channel_layer_redis, make_layer
):
    layer = make_layer(group_expiry=900)
    await layer.group_add("table-1", CHANNEL)
    joined = channel_layer_redis.zscore(GROUP_KEY, CHANNEL)
    async with receiving(layer, CHANNEL):
        pass

    # Right after the consumer stopped waiting it may just be handling a message.
    await layer.renew_group_memberships()
    renewed = channel_layer_redis.zscore(GROUP_KEY, CHANNEL)
    assert renewed >= joined

    later = time.monotonic() + layer.group_renewal_interval + 1
    with patch("baserow.ws.channel_layer.time.monotonic", return_value=later):
        await layer.renew_group_memberships()
    assert channel_layer_redis.zscore(GROUP_KEY, CHANNEL) == renewed


@pytest.mark.asyncio
async def test_groups_are_renewed_again_when_the_channel_is_received_on_again(
    channel_layer_redis, make_layer
):
    layer = make_layer(group_expiry=900)
    await layer.group_add("table-1", CHANNEL)
    later = time.monotonic() + layer.group_renewal_interval + 1
    with patch("baserow.ws.channel_layer.time.monotonic", return_value=later):
        await layer.renew_group_memberships()
    # The membership expired in the meantime.
    channel_layer_redis.delete(GROUP_KEY)

    async with receiving(layer, CHANNEL):
        await layer.renew_group_memberships()

    assert channel_layer_redis.zrange(GROUP_KEY, 0, -1) == [CHANNEL.encode()]


@pytest.mark.asyncio
async def test_a_channel_that_stays_abandoned_is_forgotten(
    channel_layer_redis, make_layer
):
    layer = make_layer(group_expiry=900)
    await layer.group_add("table-1", CHANNEL)
    much_later = time.monotonic() + 900 * 5
    with patch("baserow.ws.channel_layer.time.monotonic", return_value=much_later):
        await layer.renew_group_memberships()
    channel_layer_redis.delete(GROUP_KEY)

    async with receiving(layer, CHANNEL):
        await layer.renew_group_memberships()

    assert not channel_layer_redis.exists(GROUP_KEY)


@pytest.mark.asyncio
async def test_discarded_groups_are_not_renewed(channel_layer_redis, make_layer):
    layer = make_layer(group_expiry=900)
    await layer.group_add("table-1", CHANNEL)
    await layer.group_add("table-2", CHANNEL)
    await layer.group_discard("table-1", CHANNEL)

    async with receiving(layer, CHANNEL):
        await layer.renew_group_memberships()

    assert not channel_layer_redis.exists(GROUP_KEY)
    assert channel_layer_redis.zcard("asgi:group:table-2") == 1


@pytest.mark.asyncio
async def test_groups_are_renewed_periodically(channel_layer_redis, make_layer):
    # Renewed every third of a second.
    layer = make_layer(group_expiry=1)
    await layer.group_add("table-1", CHANNEL)

    async with receiving(layer, CHANNEL):
        channel_layer_redis.delete(GROUP_KEY)
        await asyncio.sleep(0.5)
        assert channel_layer_redis.zcard(GROUP_KEY) == 1

        # It keeps going after a failure, which adds the memberships again.
        with patch.object(
            RetryingRedisChannelLayer, "connection", side_effect=ConnectionError()
        ):
            await asyncio.sleep(0.5)
        channel_layer_redis.delete(GROUP_KEY)
        await asyncio.sleep(0.5)
        assert channel_layer_redis.zcard(GROUP_KEY) == 1


@pytest.mark.asyncio
async def test_a_group_discarded_during_a_renewal_is_not_added_again(
    channel_layer_redis, make_layer
):
    layer = make_layer(group_expiry=900)
    await layer.group_add("table-1", CHANNEL)
    await layer.group_add("table-2", CHANNEL)
    last_group = list(layer._group_memberships[CHANNEL])[-1]

    async with receiving(layer, CHANNEL):
        with patch("baserow.ws.channel_layer.GROUP_RENEWAL_BATCH_SIZE", 1):
            renewal = asyncio.ensure_future(layer.renew_group_memberships())
            await asyncio.sleep(0)
            await layer.group_discard(last_group, CHANNEL)
            await renewal

    assert channel_layer_redis.zscore(f"asgi:group:{last_group}", CHANNEL) is None
