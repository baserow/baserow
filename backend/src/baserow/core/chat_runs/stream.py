"""Replay and follow background chat-run output over HTTP."""

import asyncio
from typing import Any, AsyncIterator, Callable
from uuid import UUID

from django.contrib.auth.models import AbstractUser
from django.db import DEFAULT_DB_ALIAS, connections

from asgiref.sync import sync_to_async
from redis.exceptions import RedisError

from baserow.config.db_routers import clear_db_state, set_db_alias

from .buffer import (
    READ_BLOCK_MILLISECONDS,
    ChatRunBuffer,
    ReplayUnavailable,
    parse_cursor,
    stream_id_key,
)
from .constants import ChatRunEventKind
from .handler import ChatRunHandler
from .models import ACTIVE_CHAT_RUN_STATUSES
from .service import ChatRunService, serialize_run

STATUS_INTERVAL_SECONDS = 5.0
OUTPUT_ERRORS = (ReplayUnavailable, ConnectionError, TimeoutError, OSError, RedisError)


def _read_state(run_id: UUID, reader: AbstractUser | None) -> dict:
    """
    Read the run's saved state from the primary, in a short pool thread.

    :param run_id: The id of the run.
    :param reader: When given, the user whose read permission is checked first.
    :return: The serialized run.
    """

    try:
        set_db_alias(DEFAULT_DB_ALIAS)
        if reader is None:
            return serialize_run(ChatRunHandler().get_run(run_id))
        return ChatRunService().snapshot(reader, run_id)
    finally:
        clear_db_state()
        connections.close_all()


def _fold(events: list[dict]) -> dict:
    text, segment, progress, variant = "", None, None, None
    for event in events:
        data = event["data"]
        if event["kind"] == ChatRunEventKind.TEXT_DELTA:
            if segment != data["segment"]:
                text, segment = "", data["segment"]
            text += data["text"]
            variant = data.get("variant")
        elif event["kind"] == ChatRunEventKind.PROGRESS:
            progress = data
    return {"text": text, "segment": segment, "progress": progress, "variant": variant}


def _is_active(state: dict[str, Any]) -> bool:
    return state["status"] in ACTIVE_CHAT_RUN_STATUSES


def _record(
    kind: str, data: dict[str, Any], cursor: str | None, replayed: bool
) -> dict[str, Any]:
    return {"kind": kind, "data": data, "cursor": cursor, "replayed": replayed}


class _OutputReader:
    """One follower's position in a run's buffered output."""

    def __init__(self, run_id: UUID, cursor: str | None, replay: bool) -> None:
        self.buffer = ChatRunBuffer(run_id)
        self.cursor = cursor
        self.replay = replay
        self.attached = False
        self.high_water: tuple[int, int] | None = None
        self.baseline_needed = bool(cursor)
        self.waiting = False

    async def read(self) -> list[dict[str, Any]]:
        """Wait for new events, or only wait once the output can't be read."""

        if self.waiting:
            await asyncio.sleep(READ_BLOCK_MILLISECONDS / 1000)
            return []
        batch = await self.buffer.read(self.cursor, block_ms=READ_BLOCK_MILLISECONDS)
        if not self.attached:
            self.attached = True
            if self.replay and batch.high_water:
                self.high_water = stream_id_key(parse_cursor(batch.high_water)[1])
        return batch.events

    async def baseline(self) -> dict[str, Any] | None:
        """Fold the output before the resume cursor into one record, once."""

        if self.waiting or not self.baseline_needed:
            return None
        prefix = await self.buffer.recover(self.cursor)
        if prefix is None:
            raise ReplayUnavailable("prefix")
        self.baseline_needed = False
        return _record("run.baseline", _fold(prefix), self.cursor, replayed=True)

    def unavailable(self, error: Exception) -> dict[str, Any] | None:
        """Retry an outage or a buffer not started yet, else stop with a notice."""

        reason = error.reason if isinstance(error, ReplayUnavailable) else "connection"
        if reason == "connection" or (reason == "missing" and self.cursor is None):
            return None
        self.waiting = True
        return _record(
            "run.replay_unavailable", {"reason": reason}, self.cursor, replayed=True
        )

    def heartbeat(self) -> dict[str, Any]:
        return _record(ChatRunEventKind.RUN_HEARTBEAT, {}, self.cursor, replayed=False)

    def relay(self, event: dict[str, Any]) -> dict[str, Any]:
        position = stream_id_key(parse_cursor(event["cursor"])[1])
        replayed = self.high_water is not None and position <= self.high_water
        return {**event, "replayed": replayed}


async def follow_run(
    run: Any,
    user: Any,
    cursor: str | None = None,
    *,
    replay: bool = True,
    snapshot: Callable | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """Yield ordered output, compatible heartbeats, and authoritative completion.

    The core stream view, or a product view, wraps this iterator in its streaming
    HTTP response. Its body runs when the HTTP server consumes that response on the
    web process's event loop, not when the view creates the iterator and not in the
    Celery worker. Closing the response closes this follower, leaving the worker
    running.

    Read permission is checked once, when the stream opens; a reconnect checks it
    again. Afterwards the saved state is read only on ``run.finished`` or after
    ``STATUS_INTERVAL_SECONDS`` without output, because a live run ends its own
    stream. Redis failures never restart work, and never prevent durable recovery.

    :param run: The run to follow.
    :param user: The user reading the run.
    :param cursor: The last cursor the client saw, or None to read from the start.
    :param replay: False only for the response that created a brand-new run.
    :param snapshot: Async callback replacing the saved-state reads, for tests.
    :return: The output records, in order, ending with ``run.finished``.
    """

    if cursor:
        parse_cursor(cursor)

    async def read_state(reader: AbstractUser | None = None) -> dict:
        if snapshot is not None:
            return await snapshot()
        return await sync_to_async(_read_state, thread_sensitive=False)(run.id, reader)

    loop = asyncio.get_running_loop()
    output = _OutputReader(run.id, cursor, replay)
    state = await read_state(user)
    next_status = loop.time() + STATUS_INTERVAL_SECONDS
    while _is_active(state):
        if loop.time() >= next_status:
            state = await read_state()
            next_status = loop.time() + STATUS_INTERVAL_SECONDS
            continue
        try:
            events = await output.read()
            if baseline := await output.baseline():
                yield baseline
        except OUTPUT_ERRORS as error:
            yield output.unavailable(error) or output.heartbeat()
            await asyncio.sleep(min(1.0, STATUS_INTERVAL_SECONDS))
            continue
        if not events:
            yield output.heartbeat()
            continue
        # Only a quiet stream needs Postgres: a live run appends run.finished.
        next_status = loop.time() + STATUS_INTERVAL_SECONDS
        for event in events:
            output.cursor = event["cursor"]
            if event["kind"] != ChatRunEventKind.RUN_FINISHED:
                yield output.relay(event)
            elif not _is_active(state := await read_state()):
                break
        # Do not pin a replay page while the next read blocks.
        events = event = None
    yield _record(ChatRunEventKind.RUN_FINISHED, state, output.cursor, replayed=True)
