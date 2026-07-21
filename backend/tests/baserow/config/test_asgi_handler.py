import asyncio

import pytest

from baserow.config.helpers import BaserowASGIHandler


@pytest.mark.asyncio
async def test_listen_for_disconnect_returns_instead_of_raising():
    handler = BaserowASGIHandler.__new__(BaserowASGIHandler)

    async def receive():
        return {"type": "http.disconnect"}

    assert await handler.listen_for_disconnect(receive) is None


@pytest.mark.asyncio
async def test_listen_for_disconnect_still_asserts_on_invalid_message():
    handler = BaserowASGIHandler.__new__(BaserowASGIHandler)

    async def receive():
        return {"type": "http.unexpected"}

    with pytest.raises(AssertionError):
        await handler.listen_for_disconnect(receive)


@pytest.mark.asyncio
async def test_handle_cancels_in_flight_request_on_disconnect():
    """
    With a disconnect listener that completes normally instead of raising, `handle()`
    must still cancel the in-flight request on disconnect. This holds on Django 5.2 but
    not on Django >= 6.1 (TaskGroup based), where only a raising listener aborts the
    request. If this test fails after a Django upgrade, the `listen_for_disconnect`
    override must be reworked.
    """

    handler = BaserowASGIHandler()

    request_started = asyncio.Event()
    request_cancelled = False

    async def fake_run_get_response(request):
        nonlocal request_cancelled
        request_started.set()
        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            request_cancelled = True
            raise

    handler.run_get_response = fake_run_get_response

    body_messages = [{"type": "http.request", "body": b"", "more_body": False}]

    async def receive():
        if body_messages:
            return body_messages.pop(0)
        # Only disconnect once the request is actually in flight, so the cancellation
        # path is deterministically exercised.
        await request_started.wait()
        return {"type": "http.disconnect"}

    sent_messages = []

    async def send(message):
        sent_messages.append(message)

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [],
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 1000),
        "scheme": "http",
    }

    await asyncio.wait_for(handler(scope, receive, send), timeout=10)

    assert request_cancelled is True
    # The request never completed, so nothing must have been sent.
    assert sent_messages == []
