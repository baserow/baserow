import asyncio
import json
import threading
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

from django.contrib.auth import get_user_model

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator
from rest_framework_simplejwt.settings import api_settings as jwt_settings
from rest_framework_simplejwt.tokens import AccessToken

from baserow.config.asgi import application
from baserow.core.models import UserProfile
from baserow.ws.telemetry import run_sync


@asynccontextmanager
async def shared_executor_blocked():
    """Occupy the actual shared executor without a slow database or a sleep."""

    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    release = threading.Event()

    def blocking_operation():
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5), "Test did not release the shared executor"

    task = asyncio.create_task(run_sync("page_permission", blocking_operation))
    try:
        await asyncio.wait_for(started.wait(), 2)
        yield
    finally:
        release.set()
        await asyncio.wait_for(task, 2)


async def receive_while_executor_blocked(communicator):
    # Communicator.receive_output cancels the whole application on timeout.
    # Cancel only this queue reader so the finally block can cleanly disconnect.
    reader = asyncio.create_task(communicator.output_queue.get())
    try:
        done, _ = await asyncio.wait({reader}, timeout=0.5)
        assert done, "An unrelated shared-thread operation blocked WebSocket dispatch"
        return reader.result()
    finally:
        if not reader.done():
            reader.cancel()
        await asyncio.gather(reader, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.websockets
@pytest.mark.parametrize("authentication", ["anonymous", "cached_user"])
async def test_handshake_does_not_wait_for_shared_executor(
    settings, monkeypatch, authentication
):
    settings.PRESENCE_VISIBLE_USERS = 0
    settings.DISABLE_ANONYMOUS_PUBLIC_VIEW_WS_CONNECTIONS = False
    token = "anonymous"
    if authentication == "cached_user":
        # Stub only the async cache boundary. Token verification and the loaded
        # user's validity checks run normally, without requiring a database.
        user = get_user_model()(id=42, is_active=True)
        UserProfile(user=user)
        cached_user = AsyncMock(return_value=user)
        monkeypatch.setattr("baserow.ws.auth.aget_cached_user", cached_user)
        access_token = AccessToken()
        access_token[jwt_settings.USER_ID_CLAIM] = user.id
        token = str(access_token)

    communicator = WebsocketCommunicator(application, f"ws/core/?jwt_token={token}")
    try:
        async with shared_executor_blocked():
            await communicator.send_input({"type": "websocket.connect"})
            accepted = await receive_while_executor_blocked(communicator)
            assert accepted["type"] == "websocket.accept"
            authenticated = await receive_while_executor_blocked(communicator)
            payload = json.loads(authenticated["text"])
            assert payload["type"] == "authentication"
            assert payload["success"] is True
            if authentication == "cached_user":
                cached_user.assert_awaited_once_with(user.id)
    finally:
        await communicator.disconnect(timeout=2)


@pytest.mark.asyncio
@pytest.mark.websockets
@pytest.mark.parametrize("event_kind", ["live", "presence", "force_disconnect"])
async def test_delivery_does_not_wait_for_shared_executor(settings, event_kind):
    settings.PRESENCE_VISIBLE_USERS = 0
    communicator = WebsocketCommunicator(application, "ws/core/?jwt_token=anonymous")
    assert (await communicator.connect())[0]
    await communicator.receive_json_from()

    if event_kind == "live":
        payload = {"type": "test_live_event", "event_id": 123}
        event = {
            "type": "broadcast_to_users",
            "send_to_all_users": True,
            "user_ids": [],
            "ignore_web_socket_id": None,
            "payload": payload,
        }
    elif event_kind == "presence":
        payload = {"type": "presence.editors_active", "active": True}
        event = {
            "type": "broadcast_to_group",
            "ignore_web_socket_id": None,
            "payload": payload,
        }
    else:
        payload = {"type": "force_disconnect"}
        event = {
            "type": "force_disconnect_users",
            "user_ids": [None],
            "ignore_web_socket_ids": [],
        }

    try:
        async with shared_executor_blocked():
            await get_channel_layer().group_send("users", event)
            output = await receive_while_executor_blocked(communicator)
            assert json.loads(output["text"]) == payload
            if event_kind == "force_disconnect":
                closed = await receive_while_executor_blocked(communicator)
                assert closed["type"] == "websocket.close"
    finally:
        await communicator.disconnect(timeout=2)


@pytest.mark.asyncio
@pytest.mark.websockets
async def test_disconnect_releases_groups_before_shared_executor_is_available(
    settings, monkeypatch
):
    settings.PRESENCE_VISIBLE_USERS = 0
    communicator = WebsocketCommunicator(application, "ws/core/?jwt_token=anonymous")
    assert (await communicator.connect())[0]
    await communicator.receive_json_from()
    layer = get_channel_layer()
    group_discard = layer.group_discard
    discarded = asyncio.Event()

    async def discard(group, channel):
        await group_discard(group, channel)
        if group == "users":
            discarded.set()

    monkeypatch.setattr(layer, "group_discard", discard)
    try:
        async with shared_executor_blocked():
            await communicator.send_input(
                {"type": "websocket.disconnect", "code": 1000}
            )
            await asyncio.wait_for(discarded.wait(), 0.5)
    finally:
        # Channels retains its final connection cleanup after our async teardown.
        # Release the executor before waiting for the application to terminate.
        await communicator.wait(timeout=2)
