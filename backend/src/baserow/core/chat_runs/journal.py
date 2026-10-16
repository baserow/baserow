import asyncio
import json
import threading
from typing import Any, Callable

from django.db import connections

from asgiref.sync import sync_to_async
from loguru import logger

from .buffer import ChatRunBuffer
from .constants import (
    FLUSH_INTERVAL_SECONDS,
    LEASE_RENEW_INTERVAL_SECONDS,
    PROGRESS,
    RUN_CANCEL_REQUESTED,
    RUN_FINISHED,
    STOP_CANCELLED,
    STOP_LOST,
    TEXT_DELTA,
)
from .handler import ChatRunHandler
from .models import ChatRun

PendingEvent = tuple[str, dict[str, Any]]
MAX_PENDING_BYTES = 1024 * 1024
MAX_PENDING_EVENTS = 1024


def coalesce_events(events: list[PendingEvent]) -> list[PendingEvent]:
    """
    Shrinks a batch before it is saved: only the latest progress is kept, and
    text deltas of one segment with nothing but that progress between them
    become one. Folding the result gives the same text as folding the input.

    :param events: The pending events, in order.
    :return: The events to save, in order.
    """

    last_progress = max(
        (index for index, (kind, _) in enumerate(events) if kind == PROGRESS),
        default=None,
    )
    merged: list[PendingEvent] = []
    for index, (kind, data) in enumerate(events):
        if kind == PROGRESS and index != last_progress:
            continue
        previous_index = len(merged) - 1
        if previous_index >= 0 and merged[previous_index][0] == PROGRESS:
            previous_index -= 1
        previous = merged[previous_index] if previous_index >= 0 else None
        if (
            kind == TEXT_DELTA
            and previous is not None
            and previous[0] == TEXT_DELTA
            and previous[1]["segment"] == data["segment"]
        ):
            merged[previous_index] = (
                TEXT_DELTA,
                {
                    **previous[1],
                    "text": previous[1]["text"] + data["text"],
                },
            )
            continue
        merged.append((kind, data))
    return merged


class ChatRunJournal:
    """Coalesced Redis output and independent durable lease/Stop polling.

    Output failure disables this writer instead of retaining an unbounded retry
    queue or cancelling execution. The product adapter holds the computed answer
    for terminal persistence. A disabled writer never recreates a missing prefix.
    """

    def __init__(self, run: ChatRun) -> None:
        self.run = run
        self.buffer = ChatRunBuffer(run.id)
        self.stop_requested = threading.Event()
        self._stop_reason: str | None = None
        self._stopped = asyncio.Event()
        self._wake = asyncio.Event()
        self._flush_lock = asyncio.Lock()
        self._loop = asyncio.get_running_loop()
        self._loop_thread_id = threading.get_ident()
        self._pending: list[PendingEvent] = []
        self._pending_bytes = 0
        self._text = ""
        self._segment = 0
        self._text_variant = None
        self.output_unavailable = False
        self._invalidation_attempted = False
        # Also bound callbacks waiting to reach the loop from tool threads.
        self._thread_lock = threading.Lock()
        self._thread_pending: list[tuple[Callable, tuple, int]] = []
        self._thread_bytes = 0
        self._thread_scheduled = False

    @property
    def stop_reason(self) -> str | None:
        return self._stop_reason

    def emit(
        self,
        kind: str,
        data: dict[str, Any] | None = None,
        flush_now: bool = False,
    ) -> None:
        data = data or {}
        encoded = json.dumps(data, allow_nan=False)
        self._on_loop(
            self._add, kind, json.loads(encoded), flush_now, size=len(encoded.encode())
        )

    def emit_text(self, text: str, variant: str | None = None) -> None:
        self._on_loop(
            self._add_text, text.replace("\x00", ""), variant, size=len(text.encode())
        )

    def request_stop(self, reason: str) -> None:
        if self._stop_reason is None:
            self._stop_reason = reason
        self.stop_requested.set()
        self._stopped.set()

    async def wait_for_stop(self) -> str:
        await self._stopped.wait()
        return self._stop_reason

    async def flush(self) -> None:
        async with self._flush_lock:
            if self.output_unavailable:
                await self._invalidate_output()
                return
            if not self._pending:
                return
            batch = coalesce_events(self._pending)
            self._pending = []
            self._pending_bytes = 0
            try:
                await self.buffer.append(batch)
            except Exception:
                # A timeout can mean the append committed. Never retry it, and
                # never append an incomplete suffix after an eviction/outage.
                self._disable_output()
                await self._invalidate_output()
                logger.warning("Live output unavailable for chat run {}", self.run.id)

    async def _invalidate_output(self) -> None:
        if not self._invalidation_attempted:
            self._invalidation_attempted = True
            try:
                await self.buffer.invalidate()
            except Exception:
                # One bounded attempt, independent of lease/Stop. Followers also
                # handle read outages and check the durable outcome periodically.
                pass

    async def publish_finished(self, snapshot: dict[str, Any]) -> None:
        """Call only AFTER the final outcome and status transaction committed."""

        self.emit(RUN_FINISHED, snapshot)
        await self.flush()
        if not self.output_unavailable:
            try:
                await self.buffer.finish()
            except Exception:
                logger.warning("Could not expire finished chat buffer {}", self.run.id)

    async def keep_flushing(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._wake.wait(), FLUSH_INTERVAL_SECONDS)
            except TimeoutError:
                pass
            self._wake.clear()
            await self.flush()

    async def keep_alive(self) -> None:
        """Redis reads/appends do not hold or share the lease polling task."""

        while True:
            await asyncio.sleep(LEASE_RENEW_INTERVAL_SECONDS)
            try:
                renewal = await sync_to_async(
                    self._renew_lease, thread_sensitive=False
                )()
            except Exception as exc:
                logger.error(
                    "Could not renew the lease of chat run {} ({})",
                    self.run.id,
                    type(exc).__name__,
                )
                continue
            if not renewal.alive:
                self.request_stop(STOP_LOST)
                return
            if renewal.cancel_requested and self._stop_reason is None:
                self.emit(RUN_CANCEL_REQUESTED, flush_now=True)
                self.request_stop(STOP_CANCELLED)

    def _renew_lease(self):
        try:
            return ChatRunHandler().renew_lease(self.run.id)
        finally:
            connections.close_all()

    def _disable_output(self) -> None:
        self.output_unavailable = True
        self._pending.clear()
        self._pending_bytes = 0
        # Product state lives in the adapter, not in this failed delta writer.
        self._text = ""

    def _on_loop(self, callback: Callable, *args: Any, size: int) -> None:
        if self.output_unavailable:
            return
        if threading.get_ident() == self._loop_thread_id:
            callback(*args)
            return
        with self._thread_lock:
            if (
                len(self._thread_pending) >= MAX_PENDING_EVENTS
                or self._thread_bytes + size > MAX_PENDING_BYTES
            ):
                self._thread_pending.clear()
                self._thread_bytes = 0
                self.output_unavailable = True
                self._loop.call_soon_threadsafe(self._disable_output)
                return
            self._thread_pending.append((callback, args, size))
            self._thread_bytes += size
            if not self._thread_scheduled:
                self._thread_scheduled = True
                self._loop.call_soon_threadsafe(self._drain_threads)

    def _drain_threads(self) -> None:
        with self._thread_lock:
            pending = self._thread_pending
            self._thread_pending = []
            self._thread_bytes = 0
            self._thread_scheduled = False
        for callback, args, _ in pending:
            if self.output_unavailable:
                break
            callback(*args)

    def _add(self, kind: str, data: dict[str, Any], flush_now: bool = False) -> None:
        size = len(json.dumps(data, allow_nan=False).encode()) + len(kind)
        if (
            len(self._pending) >= MAX_PENDING_EVENTS
            or self._pending_bytes + size > MAX_PENDING_BYTES
        ):
            self._disable_output()
            return
        self._pending.append((kind, data))
        self._pending_bytes += size
        if flush_now:
            self._wake.set()

    def _add_text(self, text: str, variant: str | None = None) -> None:
        extra = {"variant": variant} if variant is not None else {}
        if variant == self._text_variant and text.startswith(self._text):
            delta = text[len(self._text) :]
            if delta:
                self._add(
                    TEXT_DELTA, {"segment": self._segment, "text": delta, **extra}
                )
        else:
            self._segment += 1
            self._add(TEXT_DELTA, {"segment": self._segment, "text": text, **extra})
        if not self.output_unavailable:
            self._text = text
            self._text_variant = variant
