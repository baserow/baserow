"""
Tests for websocket broadcast tasks with oversized integer payloads.

These tests verify that the defensive normalization layer in
send_message_to_channel_group prevents OverflowError when broadcasting
payloads containing integers exceeding the msgpack serialization range.

The tests use the InMemoryChannelLayer (which does not use msgpack), but
verify that normalization is applied by checking the payload values
received by websocket clients. This confirms the normalization code path
is executed during broadcast operations.
"""

import pytest
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from unittest.mock import AsyncMock, patch

from baserow.config.asgi import application
from baserow.ws.tasks import (
    broadcast_to_channel_group,
    broadcast_to_users,
    send_message_to_channel_group,
)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_users_with_overflow_integer(data_fixture):
    """
    Verify that broadcasting a payload containing an integer exceeding
    msgpack's uint64 max succeeds and the value is received as a string.

    Without the normalization fix, this would fail with:
        OverflowError: Python int too large to convert to C unsigned long
    when using the Redis channel layer in production.
    """

    user_1, token_1 = data_fixture.create_user_and_token()

    communicator_1 = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator_1.connect()
    await communicator_1.receive_json_from()

    overflow_value = 18446744073709551616  # 2^64, exceeds msgpack uint64 max

    await sync_to_async(broadcast_to_users)(
        [user_1.id],
        {
            "type": "test_overflow",
            "data": {"big_number": overflow_value, "safe_number": 42},
        },
    )

    response = await communicator_1.receive_json_from(0.1)
    assert response["type"] == "test_overflow"
    # The oversized integer must be converted to its string representation
    assert response["data"]["big_number"] == "18446744073709551616"
    # Safe integers must remain as integers
    assert response["data"]["safe_number"] == 42

    await communicator_1.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_to_channel_group_with_overflow_integer(data_fixture):
    """
    Verify that broadcast_to_channel_group handles overflow integers
    in the payload without raising OverflowError.
    """

    user_1, token_1 = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(users=[user_1])
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    # Join the table page
    await communicator.send_json_to({"page": "table", "table_id": table.id})
    response = await communicator.receive_json_from(0.1)
    assert response["type"] == "page_add"

    overflow = 18446744073709551616

    await sync_to_async(broadcast_to_channel_group)(
        f"table-{table.id}",
        {"message": "overflow_test", "value": overflow},
    )

    response = await communicator.receive_json_from(0.1)
    assert response["message"] == "overflow_test"
    assert response["value"] == "18446744073709551616"

    await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_broadcast_nested_overflow_integers(data_fixture):
    """
    Verify that deeply nested overflow integers are normalized throughout
    the entire payload structure.
    """

    user_1, token_1 = data_fixture.create_user_and_token()

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    overflow = 18446744073709551616
    underflow = -(2**63) - 1

    await sync_to_async(broadcast_to_users)(
        [user_1.id],
        {
            "type": "nested_test",
            "body": {
                "level1": {
                    "big": overflow,
                    "items": [1, overflow, {"nested_big": underflow}],
                },
                "safe": 999,
            },
        },
    )

    response = await communicator.receive_json_from(0.1)
    assert response["type"] == "nested_test"
    body = response["body"]
    assert body["level1"]["big"] == str(overflow)
    assert body["level1"]["items"][0] == 1
    assert body["level1"]["items"][1] == str(overflow)
    assert body["level1"]["items"][2]["nested_big"] == str(underflow)
    assert body["safe"] == 999

    await communicator.disconnect()


@pytest.mark.asyncio
async def test_send_message_to_channel_group_normalizes_before_send():
    """
    Verify that send_message_to_channel_group normalizes the message
    before passing it to channel_layer.group_send. This is the critical
    defensive boundary that prevents OverflowError in production where
    channels_redis uses msgpack serialization.
    """

    mock_channel_layer = AsyncMock()
    mock_channel_layer.close_pools = AsyncMock()

    overflow = 18446744073709551616
    message = {
        "type": "test",
        "payload": {"big": overflow, "safe": 42},
    }

    await send_message_to_channel_group(mock_channel_layer, "test_group", message)

    # Verify the message was normalized before being sent
    call_args = mock_channel_layer.group_send.call_args
    sent_message = call_args[0][1]
    assert sent_message["payload"]["big"] == str(overflow)
    assert sent_message["payload"]["safe"] == 42


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_safe_payload_unaffected_by_normalization(data_fixture):
    """
    Verify that payloads containing only safe values pass through
    normalization completely unchanged. This confirms the fix does not
    break existing valid payloads.
    """

    user_1, token_1 = data_fixture.create_user_and_token()

    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token_1}",
        headers=[(b"origin", b"http://localhost")],
    )
    await communicator.connect()
    await communicator.receive_json_from()

    await sync_to_async(broadcast_to_users)(
        [user_1.id],
        {
            "type": "safe_payload",
            "integer": 42,
            "negative": -100,
            "float": 3.14,
            "string": "hello",
            "boolean": True,
            "null_val": None,
            "list": [1, 2, 3],
            "nested": {"a": 1, "b": "two"},
        },
    )

    response = await communicator.receive_json_from(0.1)
    assert response["type"] == "safe_payload"
    assert response["integer"] == 42
    assert response["negative"] == -100
    assert response["float"] == 3.14
    assert response["string"] == "hello"
    assert response["boolean"] is True
    assert response["null_val"] is None
    assert response["list"] == [1, 2, 3]
    assert response["nested"] == {"a": 1, "b": "two"}

    await communicator.disconnect()
