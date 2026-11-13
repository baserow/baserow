from django.test.utils import override_settings

import msgpack

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
