import asyncio
import os
from copy import deepcopy
from uuid import uuid4

import pytest
import pytest_asyncio
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.config.settings import base


@pytest_asyncio.fixture
async def redis_channel_layer(settings):
    channel_layers = deepcopy(base.CHANNEL_LAYERS)
    config = channel_layers["default"]["CONFIG"]
    # Keep production connection options: the ordinary tests replace this layer
    # with InMemoryChannelLayer and cannot catch Redis socket timeout regressions.
    config["hosts"] = [
        {**host, "address": os.environ["TEST_REDIS_URL"]}
        if isinstance(host, dict)
        else os.environ["TEST_REDIS_URL"]
        for host in config["hosts"]
    ]
    config["prefix"] = f"baserow-ws-test-{uuid4().hex}:"
    settings.CHANNEL_LAYERS = channel_layers
    channel_layer = get_channel_layer()
    try:
        await channel_layer.connection(0).ping()
        yield channel_layer
    finally:
        # RedisChannelLayer.flush removes only this layer's unique prefix and
        # closes its pools. Never flush the Redis database shared by other tests.
        await channel_layer.flush()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@pytest.mark.skipif(
    not os.environ.get("TEST_REDIS_URL"),
    reason="Set TEST_REDIS_URL to run the real Redis regression (enabled in CI).",
)
async def test_authenticated_websocket_receives_redis_event_after_idle(
    data_fixture, redis_channel_layer
):
    user, token = data_fixture.create_user_and_token()
    communicator = WebsocketCommunicator(
        application,
        f"ws/core/?jwt_token={token}&web_socket_id=redis-idle-test",
        headers=[(b"origin", b"http://localhost")],
    )
    try:
        connected, _ = await communicator.connect(timeout=5)
        assert connected is True
        authentication = await communicator.receive_json_from(timeout=5)
        assert authentication["type"] == "authentication"
        assert authentication["success"] is True

        # Exercise two full blocking reads with the real production timeout.
        # Redis-py 8's shorter default used to kill the consumer while idle.
        await asyncio.sleep(2 * redis_channel_layer.brpop_timeout + 1)
        assert not communicator.future.done(), (
            f"WebSocket stopped while idle: {communicator.future.exception()!r}"
        )

        payload = {"type": "redis_idle_regression", "message": "after idle"}
        await redis_channel_layer.group_send(
            "users",
            {
                "type": "broadcast_to_users",
                "user_ids": [user.id],
                "send_to_all_users": False,
                "ignore_web_socket_id": None,
                "payload": payload,
            },
        )
        assert await communicator.receive_json_from(timeout=5) == payload
    finally:
        # A failed consumer already contains the useful original exception.
        if not communicator.future.done():
            await communicator.disconnect(timeout=5)
