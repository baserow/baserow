from types import SimpleNamespace
from unittest.mock import patch

import pytest

from baserow.contrib.whiteboard.ws.client_message_types import (
    BroadcastWhiteboardChangesMessageType,
)


def _consumer_with(user, web_socket_id="ws-1"):
    """Lightweight stand-in for the AsyncJsonWebsocketConsumer — only
    `scope` is read by the handler."""
    return SimpleNamespace(scope={"user": user, "web_socket_id": web_socket_id})


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_handle_broadcasts_to_other_clients(data_fixture):
    user = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application(user=user)
    handler = BroadcastWhiteboardChangesMessageType()
    consumer = _consumer_with(user, web_socket_id="ws-sender")
    payload = {"type": "scene_update", "elements": [{"id": "x"}]}

    with patch(
        "baserow.contrib.whiteboard.ws.client_message_types"
        ".WhiteboardPageType.broadcast"
    ) as broadcast:
        await handler.handle(
            consumer,
            {
                "type": "broadcast_whiteboard_changes",
                "whiteboard_id": whiteboard.id,
                "payload": payload,
            },
        )

    broadcast.assert_called_once()
    args, kwargs = broadcast.call_args
    assert args[0] == payload
    assert kwargs["whiteboard_id"] == whiteboard.id
    assert kwargs["ignore_web_socket_id"] == "ws-sender"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_handle_silently_drops_when_user_lacks_permission(data_fixture):
    # Different user without workspace access.
    intruder = data_fixture.create_user()
    whiteboard = data_fixture.create_whiteboard_application()
    handler = BroadcastWhiteboardChangesMessageType()
    consumer = _consumer_with(intruder)

    with patch(
        "baserow.contrib.whiteboard.ws.client_message_types"
        ".WhiteboardPageType.broadcast"
    ) as broadcast:
        await handler.handle(
            consumer,
            {
                "type": "broadcast_whiteboard_changes",
                "whiteboard_id": whiteboard.id,
                "payload": {"type": "scene_update"},
            },
        )

    broadcast.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_handle_drops_unknown_whiteboard(data_fixture):
    user = data_fixture.create_user()
    handler = BroadcastWhiteboardChangesMessageType()
    consumer = _consumer_with(user)

    with patch(
        "baserow.contrib.whiteboard.ws.client_message_types"
        ".WhiteboardPageType.broadcast"
    ) as broadcast:
        await handler.handle(
            consumer,
            {
                "type": "broadcast_whiteboard_changes",
                "whiteboard_id": 9_999_999,
                "payload": {"type": "scene_update"},
            },
        )

    broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_handle_ignores_malformed_input():
    handler = BroadcastWhiteboardChangesMessageType()
    consumer = _consumer_with(SimpleNamespace(id=1))

    with patch(
        "baserow.contrib.whiteboard.ws.client_message_types"
        ".WhiteboardPageType.broadcast"
    ) as broadcast:
        # Missing `whiteboard_id`
        await handler.handle(
            consumer, {"type": "broadcast_whiteboard_changes", "payload": {}}
        )
        # Wrong types
        await handler.handle(
            consumer,
            {
                "type": "broadcast_whiteboard_changes",
                "whiteboard_id": "abc",
                "payload": "nope",
            },
        )

    broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_handle_drops_anonymous_user():
    handler = BroadcastWhiteboardChangesMessageType()
    consumer = _consumer_with(None)

    with patch(
        "baserow.contrib.whiteboard.ws.client_message_types"
        ".WhiteboardPageType.broadcast"
    ) as broadcast:
        await handler.handle(
            consumer,
            {
                "type": "broadcast_whiteboard_changes",
                "whiteboard_id": 1,
                "payload": {},
            },
        )

    broadcast.assert_not_called()
