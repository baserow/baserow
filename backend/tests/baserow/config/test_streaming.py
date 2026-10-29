import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from django.http import JsonResponse, StreamingHttpResponse
from django.urls import reverse

import pytest
from asgiref.sync import SyncToAsync

from baserow.config import streaming
from baserow.config.streaming import AsyncStreamingHTTPRouter


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


def _router(monkeypatch, path="/stream/", methods=("POST",), max_streams=1):
    monkeypatch.setattr(streaming, "_paths", [])
    streaming.register_async_stream_path(path, methods=methods)
    return AsyncStreamingHTTPRouter(
        AsyncMock(), max_streams=max_streams, max_streams_per_user=1
    )


class _SignedInStreams:
    """Stands in for Django: signs in the X-User header's user and streams forever."""

    def __init__(self):
        self.started = asyncio.Queue()

    def get_response(self, request):
        request.user = SimpleNamespace(
            id=int(request.headers["X-User"]), is_authenticated=True
        )
        return StreamingHttpResponse(self._hold(request.user.id))

    async def _hold(self, user_id):
        await self.started.put(user_id)
        await asyncio.Event().wait()
        yield b""


@pytest.mark.asyncio
async def test_http_stream_admission_does_not_hold_rest_capacity_or_thread_context(
    monkeypatch,
):
    router = _router(monkeypatch)
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
        streaming,
        "_prepare",
        lambda scope, body: (StreamingHttpResponse(chunks()), None),
    )
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
        AsyncMock(
            side_effect=[
                {"type": "http.request", "body": b"{}"},
                {"type": "http.disconnect"},
            ]
        ),
        AsyncMock(side_effect=rejection.append),
    )
    assert rejection[0]["status"] == 503
    assert b"access-control-allow-origin" in dict(rejection[0]["headers"])
    assert dict(rejection[0]["headers"])[b"retry-after"] == b"1"
    await router(_scope("/ordinary/", "GET"), AsyncMock(), AsyncMock())
    router.fallback.assert_awaited_once()
    await incoming.put({"type": "http.disconnect"})
    await asyncio.wait_for(active, 1)
    assert router.active == 0
    assert closed.is_set()


@pytest.mark.asyncio
async def test_one_user_cannot_hold_every_stream_slot(monkeypatch):
    router = _router(monkeypatch, max_streams=3)
    handler = _SignedInStreams()
    monkeypatch.setattr(streaming, "_handler", handler)

    async def open_stream(user_id):
        scope = _scope()
        scope["headers"] = scope["headers"] + [(b"x-user", str(user_id).encode())]
        incoming = asyncio.Queue()
        await incoming.put({"type": "http.request", "body": b"{}"})
        output = []
        stream = asyncio.create_task(
            router(scope, incoming.get, AsyncMock(side_effect=output.append))
        )
        return stream, incoming, output

    first, first_incoming, _ = await open_stream(1)
    assert await asyncio.wait_for(handler.started.get(), 1) == 1
    refused, _, refusal = await open_stream(1)
    await asyncio.wait_for(refused, 1)
    assert refusal[0]["status"] == 429
    assert json.loads(refusal[-1]["body"])["error"] == "ERROR_CHAT_STREAM_USER_LIMIT"
    other, other_incoming, _ = await open_stream(2)
    assert await asyncio.wait_for(handler.started.get(), 1) == 2
    assert router.active_by_user == {1: 1, 2: 1}

    await first_incoming.put({"type": "http.disconnect"})
    await asyncio.wait_for(first, 1)
    assert router.active_by_user == {2: 1}
    await other_incoming.put({"type": "http.disconnect"})
    await asyncio.wait_for(other, 1)
    assert router.active_by_user == {}
    assert router.active == 0


@pytest.mark.asyncio
async def test_failed_http_iterator_releases_admission_and_closes_response(monkeypatch):
    router = _router(monkeypatch)
    closed = []

    async def chunks():
        raise RuntimeError("broken translator")
        yield b"unreachable"

    response = StreamingHttpResponse(chunks())
    response._resource_closers.append(lambda: closed.append(True))
    monkeypatch.setattr(streaming, "_prepare", lambda scope, body: (response, None))
    incoming = asyncio.Queue()
    await incoming.put({"type": "http.request", "body": b"{}"})
    await asyncio.wait_for(router(_scope(), incoming.get, AsyncMock()), 1)
    assert router.active == 0
    assert closed == [True]


@pytest.mark.asyncio
async def test_unfinished_body_does_not_hold_a_stream_slot(monkeypatch):
    router = _router(monkeypatch)
    monkeypatch.setattr(
        streaming, "_prepare", lambda scope, body: (JsonResponse({}), None)
    )
    uploading = asyncio.Queue()
    await uploading.put({"type": "http.request", "body": b"{", "more_body": True})
    slow = asyncio.create_task(router(_scope(), uploading.get, AsyncMock()))
    await asyncio.sleep(0)
    complete = asyncio.Queue()
    await complete.put({"type": "http.request", "body": b"{}"})
    output = []
    await asyncio.wait_for(
        router(_scope(), complete.get, AsyncMock(side_effect=output.append)), 1
    )
    assert output[0]["status"] == 200
    await uploading.put({"type": "http.disconnect"})
    await asyncio.wait_for(slow, 1)
    assert router.active == 0


@pytest.mark.asyncio
async def test_request_body_size_limit_applies_to_stream_paths(monkeypatch, settings):
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 10
    path = reverse("api:user:token_auth")
    router = _router(monkeypatch, path)
    body = json.dumps({"email": "a" * 20, "password": "b"}).encode()
    scope = _scope(path)
    scope["headers"] += [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode()),
    ]
    incoming = asyncio.Queue()
    await incoming.put({"type": "http.request", "body": body})
    output = []
    await asyncio.wait_for(
        router(scope, incoming.get, AsyncMock(side_effect=output.append)), 2
    )
    assert output[0]["status"] == 413
    assert json.loads(output[-1]["body"])["error"] == "ERROR_REQUEST_BODY_TOO_LARGE"


@pytest.mark.asyncio
async def test_nonstream_validation_response_is_preserved(monkeypatch):
    router = _router(monkeypatch)
    response = JsonResponse({"error": "ERROR_REQUEST_BODY_VALIDATION"}, status=400)
    monkeypatch.setattr(streaming, "_prepare", lambda scope, body: (response, None))
    incoming = asyncio.Queue()
    await incoming.put({"type": "http.request", "body": b"{}"})
    output = []
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
    router = _router(monkeypatch, path, methods=("GET",))
    incoming = asyncio.Queue()
    await incoming.put({"type": "http.request", "body": b"{}"})
    output = []
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
