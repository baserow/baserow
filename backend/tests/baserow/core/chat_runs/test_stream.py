import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from django.http import JsonResponse, StreamingHttpResponse
from django.urls import reverse

import pytest
from asgiref.sync import SyncToAsync

from baserow.core.chat_runs import stream
from baserow.core.chat_runs.buffer import MAX_BUFFER_EVENTS, ChatRunBuffer
from baserow.core.chat_runs.stream import ChatRunHTTPRouter, follow_run


@pytest.mark.asyncio
async def test_resume_baseline_survives_appends_and_suppresses_catchup_effects(
    buffer_redis, monkeypatch
):
    run = SimpleNamespace(id=uuid4())
    writer = ChatRunBuffer(run.id)
    prefix = await writer.append(
        [
            ("run.started", {}),
            ("text.delta", {"segment": 0, "text": "Hello"}),
        ]
    )
    await writer.append(
        [
            ("navigation", {"location": "table"}),
            ("text.delta", {"segment": 0, "text": " there"}),
        ]
    )
    original_xrange = buffer_redis.xrange
    appended = False

    async def append_during_reconstruction(*args, **kwargs):
        nonlocal appended
        rows = await original_xrange(*args, **kwargs)
        if kwargs.get("count") == MAX_BUFFER_EVENTS + 1 and not appended:
            appended = True
            await writer.append([("text.delta", {"segment": 0, "text": " live"})])
        return rows

    monkeypatch.setattr(buffer_redis, "xrange", append_during_reconstruction)
    follower = follow_run(
        run,
        None,
        prefix[-1]["cursor"],
        snapshot=AsyncMock(return_value={"status": "running"}),
    )
    try:
        baseline = await anext(follower)
        navigation = await anext(follower)
        text = await anext(follower)
        assert baseline["kind"] == "run.baseline"
        assert baseline["data"]["text"] == "Hello"
        assert navigation["kind"] == "navigation"
        assert navigation["replayed"]
        assert text["data"]["text"] == " there"
        assert text["replayed"]
        concurrent = await anext(follower)
        assert concurrent["data"]["text"] == " live"
        assert not concurrent["replayed"]
        await writer.append([("navigation", {"location": "new-table"})])
        live = await anext(follower)
        assert live["kind"] == "navigation"
        assert not live["replayed"]
    finally:
        await follower.aclose()


@pytest.mark.asyncio
async def test_new_send_treats_its_own_fast_worker_output_as_live():
    run = SimpleNamespace(id=uuid4())
    await ChatRunBuffer(run.id).append(
        [("run.started", {}), ("navigation", {"location": "table"})]
    )
    follower = follow_run(
        run, None, replay=False, snapshot=AsyncMock(return_value={"status": "running"})
    )
    try:
        assert not (await anext(follower))["replayed"]
        assert not (await anext(follower))["replayed"]
    finally:
        await follower.aclose()


@pytest.mark.asyncio
async def test_missing_replay_waits_for_durable_outcome_without_reexecuting(
    monkeypatch,
):
    monkeypatch.setattr(stream, "STATUS_INTERVAL_SECONDS", 0.001)
    run = SimpleNamespace(id=uuid4())
    snapshot = AsyncMock(
        side_effect=[
            {"status": "running"},
            {"status": "completed", "message": {"id": 7, "content": "answer"}},
        ]
    )
    records = [record async for record in follow_run(run, None, snapshot=snapshot)]
    assert [record["kind"] for record in records] == [
        "run.replay_unavailable",
        "run.finished",
    ]
    assert records[-1]["data"]["message"]["id"] == 7


@pytest.mark.asyncio
async def test_durable_terminal_wins_over_late_redis_output():
    run = SimpleNamespace(id=uuid4())
    await ChatRunBuffer(run.id).append(
        [("run.started", {}), ("text.delta", {"segment": 0, "text": "stale"})]
    )
    records = [
        record
        async for record in follow_run(
            run,
            None,
            snapshot=AsyncMock(
                return_value={
                    "status": "failed",
                    "error_code": "interrupted",
                    "message": None,
                }
            ),
        )
    ]
    assert len(records) == 1
    assert records[0]["kind"] == "run.finished"
    assert records[0]["data"]["error_code"] == "interrupted"


@pytest.mark.asyncio
async def test_finished_notification_is_checked_against_durable_state():
    run = SimpleNamespace(id=uuid4())
    await ChatRunBuffer(run.id).append(
        [
            ("run.started", {}),
            (
                "run.finished",
                {"status": "completed", "message": {"content": "untrusted"}},
            ),
        ]
    )
    snapshot = AsyncMock(
        side_effect=[
            {"status": "running"},
            {"status": "failed", "message": {"content": "committed"}},
        ]
    )
    records = [record async for record in follow_run(run, None, snapshot=snapshot)]
    assert records[-1]["data"]["status"] == "failed"
    assert records[-1]["data"]["message"]["content"] == "committed"


def _scope(path="/stream/", method="POST", origin=None):
    return {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"host", b"testserver")]
        + ([(b"origin", origin.encode())] if origin else []),
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1000),
        "scheme": "http",
    }


@pytest.mark.asyncio
async def test_http_stream_admission_does_not_hold_rest_capacity_or_thread_context(
    monkeypatch,
):
    monkeypatch.setattr(stream, "_paths", [])
    stream.register_stream_path(r"/stream/")
    prepared = asyncio.Event()
    closed = asyncio.Event()
    observed_contexts = []

    async def chunks():
        observed_contexts.append(SyncToAsync.thread_sensitive_context.get(None))
        prepared.set()
        try:
            await asyncio.Event().wait()
            yield b"unused"
        finally:
            closed.set()

    monkeypatch.setattr(
        stream, "_prepare", lambda scope, body: StreamingHttpResponse(chunks())
    )
    fallback = AsyncMock()
    router = ChatRunHTTPRouter(fallback, max_followers=1)
    incoming = asyncio.Queue()
    await incoming.put({"type": "http.request", "body": b"{}"})
    output = []
    active = asyncio.create_task(
        router(_scope(), incoming.get, AsyncMock(side_effect=output.append))
    )
    await asyncio.wait_for(prepared.wait(), 1)
    assert router.active == 1
    assert observed_contexts == [None]

    rejection = []
    await router(
        _scope(origin="https://frontend.example"),
        AsyncMock(),
        AsyncMock(side_effect=rejection.append),
    )
    assert rejection[0]["status"] == 503
    assert b"access-control-allow-origin" in dict(rejection[0]["headers"])
    assert dict(rejection[0]["headers"])[b"retry-after"] == b"1"
    await router(_scope("/ordinary/", "GET"), AsyncMock(), AsyncMock())
    fallback.assert_awaited_once()
    await incoming.put({"type": "http.disconnect"})
    await asyncio.wait_for(active, 1)
    assert router.active == 0
    assert closed.is_set()


@pytest.mark.asyncio
async def test_failed_http_iterator_releases_admission_and_closes_response(monkeypatch):
    monkeypatch.setattr(stream, "_paths", [])
    stream.register_stream_path(r"/stream/")
    closed = []

    async def chunks():
        raise RuntimeError("broken translator")
        yield b"unreachable"

    response = StreamingHttpResponse(chunks())
    response._resource_closers.append(lambda: closed.append(True))
    monkeypatch.setattr(stream, "_prepare", lambda scope, body: response)
    incoming = asyncio.Queue()
    await incoming.put({"type": "http.request", "body": b"{}"})
    router = ChatRunHTTPRouter(AsyncMock(), max_followers=1)
    await asyncio.wait_for(router(_scope(), incoming.get, AsyncMock()), 1)
    assert router.active == 0
    assert closed == [True]


@pytest.mark.asyncio
@pytest.mark.parametrize("incomplete,status", [(True, 408), (False, 413)])
async def test_initial_body_limits_release_admission_before_authentication(
    monkeypatch, incomplete, status
):
    monkeypatch.setattr(stream, "_paths", [])
    stream.register_stream_path(r"/stream/")
    monkeypatch.setattr(stream, "REQUEST_BODY_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(stream, "MAX_BODY_BYTES", 3)
    prepare = Mock()
    monkeypatch.setattr(stream, "_prepare", prepare)
    incoming = asyncio.Queue()
    await incoming.put(
        {
            "type": "http.request",
            "body": b"{" if incomplete else b"1234",
            "more_body": incomplete,
        }
    )
    output = []
    router = ChatRunHTTPRouter(AsyncMock(), max_followers=1)
    await asyncio.wait_for(
        router(
            _scope(origin="https://frontend.example"),
            incoming.get,
            AsyncMock(side_effect=output.append),
        ),
        1,
    )
    assert output[0]["status"] == status
    headers = dict(output[0]["headers"])
    assert b"access-control-allow-origin" in headers
    assert headers[b"x-content-type-options"] == b"nosniff"
    assert router.active == 0
    prepare.assert_not_called()


@pytest.mark.asyncio
async def test_nonstream_validation_response_is_preserved(monkeypatch):
    monkeypatch.setattr(stream, "_paths", [])
    stream.register_stream_path(r"/stream/")
    response = JsonResponse({"error": "ERROR_REQUEST_BODY_VALIDATION"}, status=400)
    monkeypatch.setattr(stream, "_prepare", lambda scope, body: response)
    incoming = asyncio.Queue()
    await incoming.put({"type": "http.request", "body": b"{}"})
    output = []
    router = ChatRunHTTPRouter(AsyncMock())
    await asyncio.wait_for(
        router(_scope(), incoming.get, AsyncMock(side_effect=output.append)), 1
    )
    assert output[0]["status"] == 400
    assert output[-1]["body"] == response.content
    assert router.active == 0


@pytest.mark.asyncio
async def test_detached_preparation_preserves_real_django_authentication_and_cors(
    monkeypatch,
):
    path = reverse("api:chat_runs:detail", kwargs={"run_id": uuid4()})
    monkeypatch.setattr(stream, "_paths", [])
    stream.register_stream_path(path, methods=("GET",))
    incoming = asyncio.Queue()
    await incoming.put({"type": "http.request", "body": b"{}"})
    output = []
    router = ChatRunHTTPRouter(AsyncMock())
    await asyncio.wait_for(
        router(
            _scope(path, method="GET", origin="https://frontend.example"),
            incoming.get,
            AsyncMock(side_effect=output.append),
        ),
        2,
    )
    assert output[0]["status"] == 401
    headers = dict(output[0]["headers"])
    assert b"access-control-allow-origin" in headers
    assert headers[b"x-content-type-options"] == b"nosniff"
    assert router.active == 0
