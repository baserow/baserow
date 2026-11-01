"""Shared HTTP streaming outside Django's request-lifetime executor."""

import asyncio
import io
import re
from contextlib import suppress
from typing import IO

from django.core import signals
from django.core.exceptions import ImproperlyConfigured, RequestAborted
from django.core.handlers.asgi import ASGIHandler, ASGIRequest
from django.core.handlers.base import BaseHandler
from django.db import connections
from django.http import JsonResponse
from django.middleware.security import SecurityMiddleware
from django.urls import URLPattern, URLResolver, get_resolver

from asgiref.sync import sync_to_async
from corsheaders.middleware import CorsMiddleware
from loguru import logger

from baserow.config.db_routers import clear_db_state
from baserow.middleware import BaserowCredentialedCorsMiddleware

_url_names: dict[str, tuple[str, ...]] = {}
_handler: BaseHandler | None = None


def register_async_stream_path(
    url_name: str, methods: tuple[str, ...] = ("POST",)
) -> None:
    """Register a named streaming URL during app startup, before requests arrive.

    The router still calls the product's normal Django view, which remains
    responsible for authentication, permissions and request validation.

    :param url_name: The namespaced Django URL name, e.g. ``api:chat_runs:stream``.
    :param methods: The HTTP methods to stream; other methods use the REST path.
    """

    _url_names[url_name] = methods


def _url_regex(url_name: str) -> re.Pattern:
    """Compile the full path regex of a named URL from the URLconf.

    ``reverse`` only builds one concrete URL, so this walks the resolver tree and
    joins the patterns leading to the name, matching any of its arguments.
    """

    *namespaces, name = url_name.split(":")

    def find(
        entries: list[URLPattern | URLResolver], namespaces: list[str], prefix: str
    ) -> str | None:
        for entry in entries:
            regex = prefix + entry.pattern.regex.pattern.removeprefix("^")
            if isinstance(entry, URLPattern):
                if not namespaces and entry.name == name:
                    return regex
                continue
            if entry.namespace is None:
                remaining = namespaces
            elif namespaces[:1] == [entry.namespace]:
                remaining = namespaces[1:]
            else:
                continue
            if found := find(entry.url_patterns, remaining, regex):
                return found
        return None

    regex = find(get_resolver().url_patterns, namespaces, "/")
    if regex is None:
        raise ImproperlyConfigured(f"No URL named {url_name!r} to stream.")
    return re.compile(regex)


def _prepare(scope: dict, body_file: IO[bytes]):
    """Run Django middleware/view in the web process's thread pool, then close DBs."""

    global _handler
    try:
        signals.request_started.send(sender=AsyncStreamingHTTPRouter, scope=scope)
        if _handler is None:
            handler = BaseHandler()
            handler.load_middleware(is_async=False)
            _handler = handler
        request = ASGIRequest(scope, body_file)
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


def _capacity_response(scope: dict):
    request = ASGIRequest(scope, io.BytesIO())
    response = JsonResponse({"error": "ERROR_CHAT_STREAM_CAPACITY"}, status=503)
    response["Retry-After"] = "1"
    # Rejections happen before a view runs, but must still have the deployment's
    # actual security/CORS policy, including the narrower credentialed origins.
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
    """

    def __init__(self, fallback, *, max_streams: int):
        self.fallback = fallback
        self.max_streams = max_streams
        self.active = 0
        # Not at registration: the URLconf includes registry URLs filled by ready().
        self.paths = [
            (_url_regex(url_name), methods) for url_name, methods in _url_names.items()
        ]

    async def __call__(self, scope, receive, send):
        if not any(
            scope["method"] in methods and pattern.fullmatch(scope["path"])
            for pattern, methods in self.paths
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
            response = _capacity_response(scope)
            await _send_response(response, send)
            return
        self.active += 1
        response = None
        disconnected = None
        streaming = None
        try:

            async def wait_for_disconnect():
                while (await receive())["type"] != "http.disconnect":
                    pass

            disconnected = asyncio.create_task(wait_for_disconnect())
            # An already authorized send may commit after a disconnect. Finish its
            # short preparation, close the response, and leave the worker running.
            response = await sync_to_async(_prepare, thread_sensitive=False)(
                scope, body_file
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
