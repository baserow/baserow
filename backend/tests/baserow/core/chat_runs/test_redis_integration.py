"""Opt-in verification against the supported Redis server, never a shared DB.

Run with BASEROW_TEST_CHAT_RUN_REDIS_URL pointing at an isolated Redis 6.2
instance. Keys are unique per test and removed individually afterwards.
"""

import asyncio
import json
import os
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from django.http import StreamingHttpResponse

import pytest
from asgiref.sync import SyncToAsync

from baserow.config.helpers import ConcurrencyLimiterASGI
from baserow.core.chat_runs import buffer as buffer_module
from baserow.core.chat_runs import stream
from baserow.core.chat_runs.buffer import ChatRunBuffer, ReplayUnavailable

REDIS_URL = os.getenv("BASEROW_TEST_CHAT_RUN_REDIS_URL")
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not REDIS_URL, reason="Requires an isolated Redis server"),
]


async def test_supported_redis_atomic_append_replay_limits_and_blocked_followers(
    settings, monkeypatch
):
    settings.REDIS_URL = REDIS_URL
    buffer_module.set_buffer_redis(None)
    writer = ChatRunBuffer(uuid4())
    client = await buffer_module.get_buffer_redis()
    followers = []
    try:
        version = (await client.info("server"))["redis_version"]
        assert tuple(map(int, version.split(".")[:2])) >= (6, 2)
        initial = await writer.append(
            [("run.created", {}), ("text.delta", {"segment": 0, "text": "Hello"})]
        )
        read_client = await buffer_module.get_buffer_redis(blocking=True)
        reader_name = f"chat-run-test-{uuid4().hex}"
        read_client.connection_pool.connection_kwargs["client_name"] = reader_name
        reader = ChatRunBuffer(writer.stream_key.split("{")[1].split("}")[0])
        assert (await reader.read()).events == initial
        followers = [
            asyncio.create_task(reader.read(initial[-1]["cursor"], block_ms=5000))
            for _ in range(100)
        ]
        async with asyncio.timeout(3):
            while True:
                # Other pytest workers can have their own blocked followers.
                # Wait for this cohort's XREADs, not the server-wide count.
                blocked = sum(
                    entry["name"] == reader_name
                    and entry["cmd"] == "xread"
                    and "b" in entry["flags"]
                    for entry in await client.client_list()
                )
                if blocked == 100:
                    break
                await asyncio.sleep(0.01)
        assert read_client.connection_pool is not client.connection_pool
        assert len(read_client.connection_pool._in_use_connections) == 100
        new = await writer.append([("text.delta", {"segment": 0, "text": " there"})])
        results = await asyncio.wait_for(asyncio.gather(*followers), 3)
        assert all(result.events == new for result in results)
        assert len(read_client.connection_pool._in_use_connections) == 0
        recovered = await writer.recover()
        assert recovered == initial + new
        monkeypatch.setattr(buffer_module, "MAX_BUFFER_EVENTS", len(recovered))
        with pytest.raises(ReplayUnavailable, match="limit"):
            await writer.append([("progress", {"text": "too much"})])
        assert await client.xlen(writer.stream_key) == len(recovered)
        assert await writer.recover() == recovered
        await writer.finish()
        assert 86390 <= await client.ttl(writer.stream_key) <= 86400
    finally:
        for task in followers:
            task.cancel()
        await asyncio.gather(*followers, return_exceptions=True)
        await client.delete(writer.meta_key, writer.stream_key)
        await buffer_module.close_buffer_redis()


async def test_hundred_http_followers_leave_rest_and_threads_available(
    settings, monkeypatch
):
    settings.REDIS_URL = REDIS_URL
    buffer_module.set_buffer_redis(None)
    monkeypatch.setattr(stream, "_paths", [])
    stream.register_stream_path(r"/chat/stream/")
    run = SimpleNamespace(id=uuid4())
    writer = ChatRunBuffer(run.id)
    await writer.append([("run.started", {})])
    threads_before = set(threading.enumerate())
    contexts = []
    delivered = [asyncio.Event() for _ in range(100)]
    queues = [asyncio.Queue() for _ in range(100)]
    tasks = []

    def scope(index=None, path="/chat/stream/"):
        return {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"host", b"testserver")],
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1000),
            "scheme": "http",
            "test_index": index,
        }

    def prepare(request_scope, body):
        async def records():
            contexts.append(SyncToAsync.thread_sensitive_context.get(None))
            async for event in stream.follow_run(
                run,
                None,
                replay=False,
                snapshot=AsyncMock(return_value={"status": "running"}),
            ):
                yield json.dumps(event).encode() + b"\n\n"

        return StreamingHttpResponse(records())

    monkeypatch.setattr(stream, "_prepare", prepare)

    async def rest_app(request_scope, receive, send):
        await asyncio.sleep(0.001)
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    router = stream.ChatRunHTTPRouter(
        ConcurrencyLimiterASGI(rest_app, max_concurrency=1), max_followers=100
    )

    def send(index):
        async def send_message(message):
            if message["type"] == "http.response.body" and b"live-token" in message.get(
                "body", b""
            ):
                delivered[index].set()

        return send_message

    client = await buffer_module.get_buffer_redis()
    try:
        for index, queue in enumerate(queues):
            await queue.put({"type": "http.request", "body": b"{}"})
            tasks.append(
                asyncio.create_task(router(scope(index), queue.get, send(index)))
            )
        async with asyncio.timeout(5):
            while len(contexts) < 100:
                await asyncio.sleep(0.01)
        assert router.active == 100
        assert all(context is None for context in contexts)
        # Preparation uses the bounded shared executor. A long response does not
        # create/hold one thread-sensitive worker per follower.
        assert len(set(threading.enumerate()) - threads_before) <= 32
        await asyncio.wait_for(
            asyncio.gather(
                *[
                    router(scope(path="/rest/"), AsyncMock(), AsyncMock())
                    for _ in range(25)
                ]
            ),
            1,
        )
        await writer.append([("text.delta", {"segment": 0, "text": "live-token"})])
        await asyncio.wait_for(
            asyncio.gather(*(event.wait() for event in delivered)), 3
        )
        for queue in queues:
            await queue.put({"type": "http.disconnect"})
        await asyncio.wait_for(asyncio.gather(*tasks), 3)
        assert router.active == 0
        read_client = await buffer_module.get_buffer_redis(blocking=True)
        assert len(read_client.connection_pool._in_use_connections) == 0
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await client.delete(writer.meta_key, writer.stream_key)
        await buffer_module.close_buffer_redis()


async def test_hundred_cursor_resumes_use_reader_pool_for_materialized_baselines(
    settings,
):
    settings.REDIS_URL = REDIS_URL
    buffer_module.set_buffer_redis(None)
    run = SimpleNamespace(id=uuid4())
    writer = ChatRunBuffer(run.id)
    initial = await writer.append(
        [
            ("run.started", {}),
            ("text.delta", {"segment": 0, "text": "prefix"}),
        ]
    )
    await writer.append(
        [
            ("navigation", {"location": "old-table"}),
            ("text.delta", {"segment": 0, "text": " tail"}),
        ]
    )
    client = await buffer_module.get_buffer_redis()
    # The writer budget may be small without limiting 100 independent readers.
    client.connection_pool.max_connections = 1
    followers = [
        stream.follow_run(
            run,
            None,
            cursor=initial[-1]["cursor"],
            snapshot=AsyncMock(return_value={"status": "running"}),
        )
        for _ in range(100)
    ]
    try:
        baselines = await asyncio.wait_for(
            asyncio.gather(*(anext(follower) for follower in followers)), 3
        )
        assert all(event["kind"] == "run.baseline" for event in baselines), [
            event for event in baselines if event["kind"] != "run.baseline"
        ]
        assert all(event["data"]["text"] == "prefix" for event in baselines)
        navigation = await asyncio.gather(*(anext(follower) for follower in followers))
        assert all(
            event["kind"] == "navigation" and event["replayed"] for event in navigation
        )
        text = await asyncio.gather(*(anext(follower) for follower in followers))
        assert all(event["data"]["text"] == " tail" for event in text)
        await writer.append([("text.delta", {"segment": 0, "text": " live"})])
        live = await asyncio.wait_for(
            asyncio.gather(*(anext(follower) for follower in followers)), 3
        )
        assert all(
            event["data"]["text"] == " live" and not event["replayed"] for event in live
        )
    finally:
        await asyncio.gather(*(follower.aclose() for follower in followers))
        await client.delete(writer.meta_key, writer.stream_key)
        await buffer_module.close_buffer_redis()
