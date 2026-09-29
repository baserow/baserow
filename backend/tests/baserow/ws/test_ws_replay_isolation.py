import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from channels.layers import get_channel_layer
from channels.testing import WebsocketCommunicator

from baserow.config.asgi import application
from baserow.ws import replay
from baserow.ws.auth import get_user
from baserow.ws.realtime_events import (
    FIRST_CONNECT_CURSOR,
    NO_REPLAY_AVAILABLE,
    ReplayEventsResult,
)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
async def test_three_fresh_connections_get_baselines_without_refresh(settings):
    settings.PRESENCE_VISIBLE_USERS = 0
    settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS = 100
    entered = [threading.Event(), threading.Event()]
    release = threading.Event()
    communicators = [
        WebsocketCommunicator(application, f"ws/core/?jwt_token={index}")
        for index in range(3)
    ]

    async def authenticate(token):
        return SimpleNamespace(id=int(token), is_authenticated=True)

    def read(user_id, *args):
        if user_id < 2:
            entered[user_id].set()
            assert release.wait(5)
        return ReplayEventsResult(False, 0, [])

    with (
        replay.ReplayExecutor(2) as executor,
        patch.object(replay, "_executor", executor),
        patch("baserow.ws.auth.get_user", side_effect=authenticate),
        patch.object(
            replay.RealtimeEventHandler, "get_replay_events_result", side_effect=read
        ),
    ):
        try:
            for index, communicator in enumerate(communicators):
                assert (await communicator.connect())[0]
                await communicator.receive_json_from()
                await communicator.send_json_to(
                    {
                        "type": "replay_events",
                        "last_seen_id": FIRST_CONNECT_CURSOR,
                        "supports_retry": True,
                    }
                )
                if index < 2:
                    assert await asyncio.to_thread(entered[index].wait, 2)

            # Both workers are occupied. The third request waits, without a
            # retry or outdated-workspace response for this ordinary burst.
            assert await communicators[2].receive_nothing(timeout=0.05)
            release.set()
            for communicator in communicators:
                assert await communicator.receive_json_from() == {
                    "type": "replay_events_result",
                    "force_refresh": False,
                    "latest_event_id": 0,
                }
        finally:
            release.set()
            for communicator in communicators:
                await communicator.disconnect(timeout=2)


@pytest.mark.asyncio
@pytest.mark.websockets
@pytest.mark.parametrize("supports_retry", [True, False, "true", None])
@pytest.mark.parametrize("cursor", [FIRST_CONNECT_CURSOR, 42])
async def test_transient_replay_failure_only_retries_for_capable_clients(
    settings, supports_retry, cursor
):
    settings.PRESENCE_VISIBLE_USERS = 0
    settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS = 100
    communicator = WebsocketCommunicator(application, "ws/core/?jwt_token=test-user")
    with (
        patch(
            "baserow.ws.auth.get_user",
            new=AsyncMock(return_value=SimpleNamespace(id=1, is_authenticated=True)),
        ),
        patch(
            "baserow.ws.consumers.get_replay_events_result",
            new=AsyncMock(
                side_effect=[
                    ReplayEventsResult(
                        True, NO_REPLAY_AVAILABLE, [], retry_after_ms=1000
                    ),
                    ReplayEventsResult(False, 43, []),
                    ReplayEventsResult(True, NO_REPLAY_AVAILABLE, []),
                ]
            ),
        ),
    ):
        assert (await communicator.connect())[0]
        await communicator.receive_json_from()
        request = {"type": "replay_events", "last_seen_id": cursor}
        if supports_retry is not None:
            request["supports_retry"] = supports_retry
        try:
            await communicator.send_json_to(request)
            response = await communicator.receive_json_from()
            if supports_retry is True:
                assert response == {
                    "type": "replay_events_retry",
                    "retry_after_ms": 1000,
                }
            else:
                assert response == {
                    "type": "replay_events_result",
                    "force_refresh": True,
                    "latest_event_id": NO_REPLAY_AVAILABLE,
                }

            # Retry can succeed on the same socket. A genuine unreplayable gap
            # still asks even capable clients to refresh, rather than retrying.
            await communicator.send_json_to(request)
            assert await communicator.receive_json_from() == {
                "type": "replay_events_result",
                "force_refresh": False,
                "latest_event_id": 43,
            }
            await communicator.send_json_to(request)
            assert (await communicator.receive_json_from())["force_refresh"] is True
        finally:
            await communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@pytest.mark.websockets
@pytest.mark.parametrize("recording", [True, False])
async def test_slow_replay_does_not_block_another_websocket(settings, recording):
    """A replay on one socket must not serialize another socket's handshake."""

    settings.PRESENCE_VISIBLE_USERS = 0
    settings.BASEROW_REALTIME_REPLAY_MAX_EVENTS = 100 if recording else 0
    entered = threading.Event()
    release = threading.Event()

    async def authenticate(token):
        if token == "replaying-user":
            return SimpleNamespace(id=1, is_authenticated=True)
        return await get_user(token)

    def blocked_replay(*args):
        entered.set()
        assert release.wait(5), "Test failed to release the simulated slow query"
        return ReplayEventsResult(True, NO_REPLAY_AVAILABLE, [])

    replaying = WebsocketCommunicator(application, "ws/core/?jwt_token=replaying-user")
    newcomer = WebsocketCommunicator(application, "ws/core/?jwt_token=anonymous")
    observer = WebsocketCommunicator(application, "ws/core/?jwt_token=anonymous")
    with (
        patch("baserow.ws.auth.get_user", side_effect=authenticate),
        patch(
            "baserow.ws.realtime_events.RealtimeEventHandler.get_replay_events_result",
            side_effect=blocked_replay,
        ),
    ):
        assert (await replaying.connect())[0]
        await replaying.receive_json_from()
        assert (await observer.connect())[0]
        await observer.receive_json_from()
        try:
            await replaying.send_json_to({"type": "replay_events", "last_seen_id": 1})
            if recording:
                assert await asyncio.to_thread(entered.wait, 2)
            # Wait on the ASGI messages ourselves: communicator.connect() cancels
            # the app on timeout, making it impossible to clean up deterministically.
            await newcomer.send_input({"type": "websocket.connect"})
            accepted = asyncio.create_task(newcomer.output_queue.get())
            done, _ = await asyncio.wait({accepted}, timeout=0.25)
            if not done:
                accepted.cancel()
                await asyncio.gather(accepted, return_exceptions=True)
            assert done, "Slow replay blocked an unrelated anonymous handshake"
            assert accepted.result()["type"] == "websocket.accept"
            await get_channel_layer().group_send(
                "users",
                {
                    "type": "broadcast_to_users",
                    "send_to_all_users": True,
                    "user_ids": [],
                    "ignore_web_socket_id": None,
                    "payload": {"type": "test_live_event"},
                },
            )
            assert await observer.receive_json_from(timeout=0.25) == {
                "type": "test_live_event"
            }
            assert not entered.is_set() or recording
        finally:
            release.set()
            await replaying.receive_json_from(timeout=2)
            await replaying.disconnect(timeout=2)
            await newcomer.disconnect(timeout=2)
            await observer.disconnect(timeout=2)
