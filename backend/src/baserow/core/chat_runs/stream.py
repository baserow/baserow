"""Shared HTTP following, detached from Django's request-lifetime executor."""

import asyncio
import io
import re
from contextlib import suppress
from typing import Any, AsyncIterator, Callable

from django.contrib.auth import get_user_model
from django.core import signals
from django.core.handlers.asgi import ASGIRequest
from django.core.handlers.base import BaseHandler
from django.db import connections
from django.http import JsonResponse
from django.middleware.security import SecurityMiddleware

from asgiref.sync import sync_to_async
from corsheaders.middleware import CorsMiddleware
from loguru import logger

from baserow.config.db_routers import clear_db_state, set_db_alias
from baserow.middleware import BaserowCredentialedCorsMiddleware

from .buffer import (
    READ_BLOCK_MILLISECONDS,
    ChatRunBuffer,
    ReplayUnavailable,
    parse_cursor,
    stream_id_key,
)
from .exceptions import ChatRunDoesNotExist
from .models import ACTIVE_CHAT_RUN_STATUSES

STATUS_INTERVAL_SECONDS = 5.0
MAX_FOLLOWERS = 100
MAX_BODY_BYTES = 2 * 1024 * 1024
REQUEST_BODY_TIMEOUT_SECONDS = 15.0
_paths: list[tuple[re.Pattern, tuple[str, ...]]] = []
_handler: BaseHandler | None = None


def register_stream_path(pattern: str, methods: tuple[str, ...] = ("POST",)) -> None:
    """A product's existing URL/view stays responsible for auth and validation."""

    entry = (re.compile(pattern), methods)
    if entry not in _paths:
        _paths.append(entry)


def _fresh_snapshot(user: Any, run_id: Any) -> dict:
    from .service import ChatRunService

    try:
        # Do not keep a cached active/permission state for a long-lived response.
        set_db_alias("default")
        fresh_user = (
            get_user_model()
            .objects.using("default")
            .select_related("profile")
            .get(pk=user.pk)
        )
        if not fresh_user.is_active:
            raise ChatRunDoesNotExist()
        return ChatRunService().snapshot(fresh_user, run_id)
    except get_user_model().DoesNotExist:
        raise ChatRunDoesNotExist() from None
    finally:
        clear_db_state()
        connections.close_all()


def _fold(events: list[dict]) -> dict:
    text, segment, progress, variant = "", None, None, None
    for event in events:
        data = event["data"]
        if event["kind"] == "text.delta":
            if segment != data["segment"]:
                text, segment = "", data["segment"]
            text += data["text"]
            variant = data.get("variant")
        elif event["kind"] == "progress":
            progress = data
    return {"text": text, "segment": segment, "progress": progress, "variant": variant}


async def follow_run(
    run: Any,
    user: Any,
    cursor: str | None = None,
    *,
    replay: bool = True,
    snapshot: Callable | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield ordered output, compatible heartbeats, and authoritative completion.

    ``snapshot`` is an optional async callback for consumers/tests with their own
    permission context; the default rechecks the product's read permission on the
    primary. Redis failures never restart work, and never prevent durable recovery.
    ``replay=False`` is only for the response which created a brand-new run.
    """

    if cursor:
        parse_cursor(cursor)
    buffer = ChatRunBuffer(run.id)

    async def get_snapshot():
        if snapshot is not None:
            return await snapshot()
        return await sync_to_async(_fresh_snapshot, thread_sensitive=False)(
            user, run.id
        )

    state = await get_snapshot()
    if state["status"] not in ACTIVE_CHAT_RUN_STATUSES:
        yield {
            "kind": "run.finished",
            "data": state,
            "cursor": cursor,
            "replayed": True,
        }
        return
    next_status = asyncio.get_running_loop().time() + STATUS_INTERVAL_SECONDS
    high_water: tuple[int, int] | None = None
    attached = False
    unavailable_reported = False
    invalid_cursor = False
    baseline_needed = bool(cursor)
    while True:
        now = asyncio.get_running_loop().time()
        if now >= next_status:
            state = await get_snapshot()
            next_status = asyncio.get_running_loop().time() + STATUS_INTERVAL_SECONDS
            if state["status"] not in ACTIVE_CHAT_RUN_STATUSES:
                yield {
                    "kind": "run.finished",
                    "data": state,
                    "cursor": cursor,
                    "replayed": True,
                }
                return
        try:
            if invalid_cursor:
                await asyncio.sleep(READ_BLOCK_MILLISECONDS / 1000)
                batch = None
            else:
                batch = await buffer.read(cursor, block_ms=READ_BLOCK_MILLISECONDS)
                if not attached:
                    if replay and batch.high_water:
                        high_water = stream_id_key(parse_cursor(batch.high_water)[1])
                    attached = True
                if baseline_needed:
                    prefix = await buffer.recover(cursor)
                    if prefix is None:
                        raise ReplayUnavailable("prefix")
                    baseline = _fold(prefix)
                    del prefix
                    yield {
                        "kind": "run.baseline",
                        "data": baseline,
                        "cursor": cursor,
                        "replayed": True,
                    }
                    del baseline
                    baseline_needed = False
            # A terminal commit may have happened while XREAD was blocked. Once
            # observed it wins; no subsequent Redis event can modify the answer.
            if asyncio.get_running_loop().time() >= next_status:
                state = await get_snapshot()
                next_status = (
                    asyncio.get_running_loop().time() + STATUS_INTERVAL_SECONDS
                )
                if state["status"] not in ACTIVE_CHAT_RUN_STATUSES:
                    yield {
                        "kind": "run.finished",
                        "data": state,
                        "cursor": cursor,
                        "replayed": True,
                    }
                    return
            had_events = bool(batch and batch.events)
            for event in batch.events if batch else []:
                cursor = event["cursor"]
                if event["kind"] == "run.finished":
                    state = await get_snapshot()
                    if state["status"] not in ACTIVE_CHAT_RUN_STATUSES:
                        yield {
                            "kind": "run.finished",
                            "data": state,
                            "cursor": cursor,
                            "replayed": True,
                        }
                        return
                    continue
                position = stream_id_key(parse_cursor(cursor)[1])
                yield {
                    **event,
                    "replayed": high_water is not None and position <= high_water,
                }
            # Do not pin the previous replay page while the next XREAD blocks.
            batch = None
            event = None
            if not had_events:
                yield {
                    "kind": "run.heartbeat",
                    "data": {},
                    "cursor": cursor,
                    "replayed": False,
                }
        except (ReplayUnavailable, ConnectionError, TimeoutError, OSError) as exc:
            reason = exc.reason if isinstance(exc, ReplayUnavailable) else "connection"
            if not unavailable_reported:
                yield {
                    "kind": "run.replay_unavailable",
                    "data": {"reason": reason},
                    "cursor": cursor,
                    "replayed": True,
                }
                unavailable_reported = True
            # A newly queued run might not have its first stream event yet. Only
            # an empty attachment may later begin with a complete new prefix.
            invalid_cursor = cursor is not None or reason not in (
                "missing",
                "connection",
            )
            await asyncio.sleep(min(1.0, STATUS_INTERVAL_SECONDS))
        except Exception as exc:
            # redis-py uses its own ConnectionError hierarchy. Keep product/auth
            # failures visible; only buffer-client failures enter waiting mode.
            from redis.exceptions import RedisError

            if not isinstance(exc, RedisError):
                raise
            if not unavailable_reported:
                yield {
                    "kind": "run.replay_unavailable",
                    "data": {"reason": "connection"},
                    "cursor": cursor,
                    "replayed": True,
                }
                unavailable_reported = True
            invalid_cursor = cursor is not None
            await asyncio.sleep(min(1.0, STATUS_INTERVAL_SECONDS))


def _prepare(scope: dict, body: bytes):
    global _handler
    try:
        signals.request_started.send(sender=ChatRunHTTPRouter, scope=scope)
        if _handler is None:
            handler = BaseHandler()
            handler.load_middleware(is_async=False)
            _handler = handler
        request = ASGIRequest(scope, io.BytesIO(body))
        return _handler.get_response(request)
    finally:
        # Django's normal ASGI context owns a thread until the iterator ends.
        # Here all middleware/view work is finished before async following starts.
        clear_db_state()
        connections.close_all()


def _close_response(response):
    try:
        response.close()
    finally:
        connections.close_all()


def _error_response(scope: dict, status: int, error: str):
    request = ASGIRequest(scope, io.BytesIO())
    response = JsonResponse({"error": error}, status=status)
    if status == 503:
        response["Retry-After"] = "1"
    # Rejections happen before a view runs, but must still have the deployment's
    # actual security/CORS policy, including the narrower credentialed origins.
    return BaserowCredentialedCorsMiddleware(
        CorsMiddleware(SecurityMiddleware(lambda request: response))
    )(request)


async def _send_response(response, send):
    headers = [
        (key.lower().encode("ascii"), value.encode("latin1"))
        for key, value in response.items()
    ]
    headers.extend(
        (b"set-cookie", cookie.output(header="").strip().encode("latin1"))
        for cookie in response.cookies.values()
    )
    await send(
        {
            "type": "http.response.start",
            "status": response.status_code,
            "headers": headers,
        }
    )
    if not response.streaming:
        await send({"type": "http.response.body", "body": response.content})
        return
    if not response.is_async:
        raise TypeError("Registered chat streams must return an async iterator")
    try:
        async for chunk in response.streaming_content:
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        await send({"type": "http.response.body", "body": b""})
    finally:
        close = getattr(response._iterator, "aclose", None)
        if close:
            await close()


class ChatRunHTTPRouter:
    """Admit long followers separately, before the ordinary REST limiter.

    Only registered methods/paths are intercepted. Preparation runs the existing
    Django middleware and view in a short worker section; waiting/token delivery
    holds neither a DB connection nor a request-specific thread-sensitive context.
    """

    def __init__(self, fallback, *, max_followers: int = MAX_FOLLOWERS):
        self.fallback = fallback
        self.max_followers = max_followers
        self.active = 0

    async def __call__(self, scope, receive, send):
        if not any(
            scope["method"] in methods and pattern.fullmatch(scope["path"])
            for pattern, methods in _paths
        ):
            return await self.fallback(scope, receive, send)
        if self.active >= self.max_followers:
            response = _error_response(scope, 503, "ERROR_CHAT_STREAM_CAPACITY")
            await _send_response(response, send)
            return
        self.active += 1
        response = None
        disconnected = None
        streaming = None
        try:
            body = bytearray()
            try:
                # Admission happens before authentication. An unfinished request
                # body must not reserve a long-lived follower slot indefinitely.
                async with asyncio.timeout(REQUEST_BODY_TIMEOUT_SECONDS):
                    while True:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        body.extend(message.get("body", b""))
                        if len(body) > MAX_BODY_BYTES or not message.get(
                            "more_body", False
                        ):
                            break
            except TimeoutError:
                response = _error_response(scope, 408, "ERROR_REQUEST_BODY_TIMEOUT")
                await _send_response(response, send)
                return
            if len(body) > MAX_BODY_BYTES:
                response = _error_response(scope, 413, "ERROR_REQUEST_BODY_TOO_LARGE")
                await _send_response(response, send)
                return

            async def wait_for_disconnect():
                while (await receive())["type"] != "http.disconnect":
                    pass

            disconnected = asyncio.create_task(wait_for_disconnect())
            # An already authorized send may commit after a disconnect. Finish its
            # short preparation, close the response, and leave the worker running.
            response = await sync_to_async(_prepare, thread_sensitive=False)(
                scope, bytes(body)
            )
            if disconnected.done():
                return
            streaming = asyncio.create_task(_send_response(response, send))
            await asyncio.wait(
                (streaming, disconnected), return_when=asyncio.FIRST_COMPLETED
            )
            if streaming.done():
                await streaming
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Chat stream HTTP response failed ({})", type(exc).__name__)
            # Headers may already be sent. Never attempt a second HTTP response.
        finally:
            try:
                for task in (streaming, disconnected):
                    if task is not None:
                        task.cancel()
                        with suppress(asyncio.CancelledError, Exception):
                            await task
                if response is not None:
                    await sync_to_async(_close_response, thread_sensitive=False)(
                        response
                    )
            finally:
                self.active -= 1
