"""Shared HTTP streaming outside Django's request-lifetime executor."""

import asyncio
import io
import re
from collections import Counter
from contextlib import suppress
from typing import IO

from django.core import signals
from django.core.exceptions import RequestAborted
from django.core.handlers.asgi import ASGIHandler, ASGIRequest
from django.core.handlers.base import BaseHandler
from django.db import connections
from django.http import HttpResponseBase, JsonResponse
from django.middleware.security import SecurityMiddleware

from asgiref.sync import sync_to_async
from asgiref.typing import ASGIApplication
from corsheaders.middleware import CorsMiddleware
from loguru import logger

from baserow.config.db_routers import clear_db_state
from baserow.middleware import BaserowCredentialedCorsMiddleware

_paths: list[tuple[re.Pattern, tuple[str, ...]]] = []
_handler: BaseHandler | None = None


def register_async_stream_path(
    pattern: str, methods: tuple[str, ...] = ("POST",)
) -> None:
    """Register a streaming URL during app startup, before requests arrive.

    The router still calls the product's normal Django view, which remains
    responsible for authentication, permissions and request validation.
    """

    entry = (re.compile(pattern), methods)
    if entry not in _paths:
        _paths.append(entry)


def _prepare(scope: dict, body_file: IO[bytes]) -> tuple[HttpResponseBase, int | None]:
    """Run Django middleware/view in the web process's thread pool, then close DBs.

    :return: The view's response and, when it streams, the signed-in user's id.
    """

    global _handler
    try:
        signals.request_started.send(sender=AsyncStreamingHTTPRouter, scope=scope)
        if _handler is None:
            handler = BaseHandler()
            handler.load_middleware(is_async=False)
            _handler = handler
        request = ASGIRequest(scope, body_file)
        response = _handler.get_response(request)
        user = getattr(request, "user", None)
        if response.streaming and user is not None and user.is_authenticated:
            return response, user.id
        return response, None
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


def _refusal_response(scope: dict, status: int, error: str) -> HttpResponseBase:
    request = ASGIRequest(scope, io.BytesIO())
    response = JsonResponse({"error": error}, status=status)
    response["Retry-After"] = "1"
    # Refusals skip the middleware stack, so they need its security and CORS headers.
    return BaserowCredentialedCorsMiddleware(
        CorsMiddleware(SecurityMiddleware(lambda request: response))
    )(request)


async def _send_response(response, send):
    """Consume the view's response iterator on the HTTP server's event loop."""

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
        raise TypeError("Registered streaming paths must return an async iterator")
    try:
        async for chunk in response.streaming_content:
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        await send({"type": "http.response.body", "body": b""})
    finally:
        close = getattr(response._iterator, "aclose", None)
        if close:
            await close()


class AsyncStreamingHTTPRouter:
    """Admit long-lived streams separately, before the ordinary REST limiter.

    The ASGI application calls this in the web process. For registered paths,
    ``__call__`` runs ``_prepare`` in a short thread-pool call for Django middleware
    and the view. It then runs ``_send_response`` on the HTTP event loop to consume
    the async iterator returned by the view, such as a chat-run follower.

    This thread pool is separate from Celery. The product view may enqueue a run;
    the router only delivers its response. Waiting for output retains neither a DB
    connection nor a request-specific thread-sensitive context. Disconnecting
    closes the response iterator; it does not cancel a Celery task.

    Each signed-in user may hold only a share of the streams, so one user can't
    take every slot and lock everyone else out.
    """

    def __init__(
        self,
        fallback: ASGIApplication,
        *,
        max_streams: int,
        max_streams_per_user: int,
    ):
        """
        :param fallback: The application that handles every other request.
        :param max_streams: How many streams this process delivers at once.
        :param max_streams_per_user: How many of them one signed-in user may hold.
        """

        self.fallback = fallback
        self.max_streams = max_streams
        self.max_streams_per_user = max_streams_per_user
        self.active = 0
        self.active_by_user: Counter[int] = Counter()

    async def __call__(self, scope, receive, send):
        if not any(
            scope["method"] in methods and pattern.fullmatch(scope["path"])
            for pattern, methods in _paths
        ):
            return await self.fallback(scope, receive, send)
        try:
            # Read before admission so a slow upload never holds a stream slot.
            # Django's body reader is stateless; reuse its normal upload handling.
            body_file = await ASGIHandler.read_body(self, receive)
        except RequestAborted:
            return
        if self.active >= self.max_streams:
            body_file.close()
            response = _refusal_response(scope, 503, "ERROR_CHAT_STREAM_CAPACITY")
            await _send_response(response, send)
            return
        self.active += 1
        response = None
        disconnected = None
        streaming = None
        counted_user_id = None
        try:

            async def wait_for_disconnect():
                while (await receive())["type"] != "http.disconnect":
                    pass

            disconnected = asyncio.create_task(wait_for_disconnect())
            # An already authorized send may commit after a disconnect. Finish its
            # short preparation, close the response, and leave the worker running.
            response, user_id = await sync_to_async(_prepare, thread_sensitive=False)(
                scope, body_file
            )
            if disconnected.done():
                return
            if user_id is not None:
                if self.active_by_user[user_id] >= self.max_streams_per_user:
                    refusal = _refusal_response(
                        scope, 429, "ERROR_CHAT_STREAM_USER_LIMIT"
                    )
                    await _send_response(refusal, send)
                    return
                self.active_by_user[user_id] += 1
                counted_user_id = user_id
            streaming = asyncio.create_task(_send_response(response, send))
            await asyncio.wait(
                (streaming, disconnected), return_when=asyncio.FIRST_COMPLETED
            )
            if streaming.done():
                await streaming
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Async stream HTTP response failed ({})", type(exc).__name__)
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
                body_file.close()
                self.active -= 1
                if counted_user_id is not None:
                    self.active_by_user[counted_user_id] -= 1
                    if not self.active_by_user[counted_user_id]:
                        del self.active_by_user[counted_user_id]
