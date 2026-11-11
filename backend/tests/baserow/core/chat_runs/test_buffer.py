import asyncio
from functools import partial
from uuid import uuid4

import pytest
from asgiref.sync import sync_to_async

from baserow.core.chat_runs import buffer as buffer_module
from baserow.core.chat_runs.buffer import ChatRunBuffer, ReplayUnavailable, parse_cursor
from baserow.core.chat_runs.handler import ChatRunHandler
from baserow.core.chat_runs.models import ChatRun


@pytest.mark.asyncio
async def test_ordered_replay_cursor_resume_and_independent_followers():
    run_id = uuid4()
    writer = ChatRunBuffer(run_id)
    initial = await writer.append(
        [("run.started", {}), ("text.delta", {"text": "Hi", "segment": 0})]
    )
    reader = ChatRunBuffer(run_id)
    replay = await reader.read()
    assert replay.events == initial
    assert replay.cursor == initial[-1]["cursor"]
    assert replay.high_water == initial[-1]["cursor"]

    first = asyncio.create_task(reader.read(replay.cursor, block_ms=1000))
    second = asyncio.create_task(
        ChatRunBuffer(run_id).read(replay.cursor, block_ms=1000)
    )
    await asyncio.sleep(0.01)
    new = await writer.append([("text.delta", {"text": " there", "segment": 0})])
    reads = await asyncio.gather(first, second)
    assert [result.events for result in reads] == [new, new]
    assert (await reader.read(new[-1]["cursor"])).events == []


@pytest.mark.asyncio
async def test_created_journal_and_terminal_writers_share_the_generation():
    run_id = uuid4()
    created = await ChatRunBuffer(run_id).append([("run.created", {})])
    journal = ChatRunBuffer(run_id)
    started = await journal.append([("run.started", {})])
    terminal = await ChatRunBuffer(run_id).append(
        [("run.finished", {"status": "completed"})]
    )
    assert (
        len(
            {parse_cursor(event["cursor"])[0] for event in created + started + terminal}
        )
        == 1
    )


@pytest.mark.asyncio
async def test_eviction_and_new_generation_never_silently_resume(buffer_redis):
    writer = ChatRunBuffer(uuid4())
    first = await writer.append([("run.started", {})])
    await buffer_redis.delete(writer.meta_key, writer.stream_key)
    with pytest.raises(ReplayUnavailable, match="missing"):
        await writer.append([("text.delta", {"segment": 0, "text": "tail"})])
    assert await buffer_redis.exists(writer.stream_key) == 0

    new = ChatRunBuffer(writer.stream_key.split("{")[1].split("}")[0])
    replacement = await new.append([("run.started", {})])
    with pytest.raises(ReplayUnavailable, match="generation"):
        await new.read(first[-1]["cursor"])
    with pytest.raises(ReplayUnavailable, match="generation"):
        await writer.append([("text.delta", {"segment": 0, "text": "tail"})])
    await writer.invalidate()
    assert (await new.read()).events == replacement


@pytest.mark.asyncio
async def test_terminal_notification_cannot_recreate_an_evicted_prefix(buffer_redis):
    writer = ChatRunBuffer(uuid4())
    with pytest.raises(ReplayUnavailable, match="missing"):
        await writer.append([("run.finished", {"status": "failed"})])
    assert await buffer_redis.exists(writer.meta_key, writer.stream_key) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "limit,value", [("MAX_BUFFER_BYTES", 90), ("MAX_BUFFER_EVENTS", 1)]
)
async def test_limit_marks_replay_unavailable_without_trimming_prefix(
    buffer_redis, monkeypatch, limit, value
):
    monkeypatch.setattr(buffer_module, limit, value)
    writer = ChatRunBuffer(uuid4())
    first = await writer.append([("run.started", {})])
    with pytest.raises(ReplayUnavailable, match="limit"):
        await writer.append([("text.delta", {"segment": 0, "text": "x" * 100})])
    stored = await buffer_redis.xrange(writer.stream_key)
    assert len(stored) == 1
    assert stored[0][0] == parse_cursor(first[0]["cursor"])[1]
    with pytest.raises(ReplayUnavailable, match="limit"):
        await writer.read()
    assert await writer.recover() == first


@pytest.mark.asyncio
@pytest.mark.parametrize("damage", ["trim", "delete_middle"])
async def test_incomplete_prefix_is_not_replay_or_worker_recovery(buffer_redis, damage):
    writer = ChatRunBuffer(uuid4())
    events = await writer.append(
        [
            ("run.started", {}),
            ("text.delta", {"segment": 0, "text": "middle"}),
            ("text.delta", {"segment": 0, "text": "tail"}),
        ]
    )
    if damage == "trim":
        await buffer_redis.xtrim(writer.stream_key, maxlen=1, approximate=False)
    else:
        await buffer_redis.xdel(writer.stream_key, parse_cursor(events[1]["cursor"])[1])
    with pytest.raises(ReplayUnavailable, match="prefix"):
        await writer.read()
    assert await writer.recover() is None


@pytest.mark.asyncio
async def test_cursor_must_exist_and_cannot_be_ahead():
    writer = ChatRunBuffer(uuid4())
    first = await writer.append([("run.started", {})])
    generation = parse_cursor(first[-1]["cursor"])[0]
    for position in ["0-1", "999999999999999-0"]:
        with pytest.raises(ReplayUnavailable, match="cursor"):
            await writer.read(f"{generation}:{position}")
    for cursor in ["bad", "x:0-0", generation + ":-1-0"]:
        with pytest.raises(ValueError):
            await writer.read(cursor)


@pytest.mark.asyncio
async def test_active_ttl_and_stable_namespace(buffer_redis):
    writer = ChatRunBuffer(uuid4())
    await writer.append([("run.started", {})])
    assert writer.meta_key.startswith("baserow:chat-runs:v1:")
    for key in [writer.meta_key, writer.stream_key]:
        assert 3500 <= await buffer_redis.ttl(key) <= 3600


@pytest.mark.asyncio
async def test_recovery_and_append_have_bounded_redis_time(monkeypatch, buffer_redis):
    writer = ChatRunBuffer(uuid4())
    await writer.append([("run.started", {})])
    monkeypatch.setattr(buffer_module, "OPERATION_TIMEOUT_SECONDS", 0.01)

    async def hung(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(buffer_redis, "eval", hung)
    with pytest.raises(TimeoutError):
        await writer.append([("run.started", {})])
    pipeline = buffer_redis.pipeline(transaction=False)
    monkeypatch.setattr(pipeline, "execute", hung)
    monkeypatch.setattr(buffer_redis, "pipeline", lambda **kwargs: pipeline)
    assert await asyncio.wait_for(writer.recover(), 0.1) is None


@pytest.mark.asyncio
async def test_follower_read_pool_fits_every_admitted_stream(settings):
    settings.ASGI_HTTP_MAX_CONCURRENT_STREAMS = 7
    buffer_module.set_buffer_redis(None)
    client = await buffer_module.get_buffer_redis(blocking=True)
    try:
        assert client.connection_pool.max_connections == 7
    finally:
        await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["publish", "publish_terminal", "recover"])
async def test_request_buffer_bridge_keeps_active_follower_pool_open(
    monkeypatch, mocker, operation
):
    buffer_module.set_buffer_redis(None)
    follower = await buffer_module.get_buffer_redis(blocking=True)
    bridge_clients = []
    closed_clients = []
    events = [{"kind": "run.created", "data": {}}]
    original_close = buffer_module.Redis.aclose

    async def close(client):
        closed_clients.append(client)
        await original_close(client)

    async def append(buffer, records):
        bridge_clients.append(await buffer_module.get_buffer_redis())

    async def recover(buffer):
        bridge_clients.append(await buffer_module.get_buffer_redis(blocking=True))
        return events

    # Real clients stay lazy: exercise pool ownership without Redis or the DB.
    monkeypatch.setattr(buffer_module.Redis, "aclose", close)
    monkeypatch.setattr(ChatRunBuffer, "append", append)
    monkeypatch.setattr(ChatRunBuffer, "recover", recover)
    mocker.patch("baserow.core.chat_runs.service.serialize_run", return_value={})
    handler = ChatRunHandler()
    run = ChatRun(id=uuid4())
    if operation == "publish":
        callback = partial(handler._publish, run, [("run.created", {})])
    elif operation == "publish_terminal":
        callback = partial(handler._publish_terminal, run)
    else:
        callback = partial(handler._recover_output, run.id)

    try:
        # Match the streaming router's synchronous view execution in HTTP.
        result = await sync_to_async(callback, thread_sensitive=False)()
        assert result == (events if operation == "recover" else None)
        assert await buffer_module.get_buffer_redis(blocking=True) is follower
        assert follower not in closed_clients
        assert len(bridge_clients) == 1
        assert bridge_clients[0] in closed_clients
    finally:
        await buffer_module.close_buffer_redis()
