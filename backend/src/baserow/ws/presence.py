"""
Ephemeral, Redis-only websocket presence transport.

One ``PresenceHandler`` is created per websocket connection (in
``CoreConsumer.connect``). It owns all Redis I/O and broadcast issuance for
presence join/leave/focus on presence-enabled pages. There are no database
models, migrations or Celery tasks involved: presence is intentionally
ephemeral.

Redis access
------------
Uses ``redis.asyncio`` with a dedicated module-level connection pool, separate
from both ``django_redis`` (sync) and the channel layer's internal pool. This
avoids two problems:

1. ``database_sync_to_async`` burns a thread from the shared executor pool
   (``min(32, cpu+4)``) per Redis call — presence is the hottest async path
   (focus updates on every cell selection) and should not compete for threads.
2. The channel layer's ``close_pools()`` workaround (channels_redis#332) tears
   down *all* cached connections after every ``group_send``. Reusing that pool
   would cause a create/destroy cycle on every presence operation.

The dedicated pool is created lazily on first use and lives for the process
lifetime.

Staleness / no heartbeat
------------------------
Per the design decision there is no client heartbeat/ping. Each entry stores a
``last_seen`` epoch second, refreshed on join and focus. ``_prune_stale``
runs opportunistically whenever a *new* user subscribes and prunes entries
older than ``PRESENCE_STALE_AFTER_SECONDS``. A clean disconnect removes the
entry immediately (the primary path); the stale sweep only catches unclean
disconnects (crash / proxy drop). Accepted trade-off: a still-connected user
who is idle (no join/focus) longer than the window can be pruned from other
users' snapshots until they next act. Deployments should set the threshold at
or above their proxy websocket idle timeout, since the proxy kills truly-idle
sockets anyway (firing a clean disconnect).
"""

import json
import time
from typing import Optional

from django.conf import settings

import redis.asyncio as aioredis
from loguru import logger

from baserow.ws.tasks import send_message_to_channel_group
from baserow.ws.types import PresenceSnapshotEntry

PRESENCE_KEY_PREFIX = "presence:"

PRESENCE_STALE_AFTER_SECONDS = getattr(
    settings, "BASEROW_PRESENCE_STALE_AFTER_SECONDS", 300
)

_async_redis: Optional[aioredis.Redis] = None


def _get_async_redis() -> aioredis.Redis:
    global _async_redis
    if _async_redis is None:
        _async_redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _async_redis


def _set_async_redis(client: Optional[aioredis.Redis]) -> None:
    """Override the async Redis client (used by tests to inject FakeAsyncRedis)."""

    global _async_redis
    _async_redis = client


class PresenceHandler:
    """
    Per-connection presence operations.

    Redis layout: one hash per presence channel at ``presence:{group_name}``,
    field = ``web_socket_id``, value = ``json({"user_id", "focus", "last_seen"})``.
    """

    def __init__(
        self, channel_layer, channel_name: str, web_socket_id: str, user_id: int
    ):
        self.channel_layer = channel_layer
        self.channel_name = channel_name
        self.web_socket_id = web_socket_id
        self.user_id = user_id

    def _key(self, group_name: str) -> str:
        return f"{PRESENCE_KEY_PREFIX}{group_name}"

    async def _read_all_entries(
        self, group_name: str
    ) -> tuple[dict[str, dict], list[str]]:
        """HGETALL → (parsed_entries, corrupt_fields). Read-only."""

        redis = _get_async_redis()
        raw = await redis.hgetall(self._key(group_name))
        entries: dict[str, dict] = {}
        corrupt: list[str] = []
        for web_socket_id, value in raw.items():
            try:
                entries[web_socket_id] = json.loads(value)
            except (ValueError, TypeError):
                corrupt.append(web_socket_id)
        return entries, corrupt

    async def _prune_stale(
        self,
        group_name: str,
        entries: dict[str, dict],
        corrupt_fields: Optional[list[str]] = None,
    ) -> dict[str, dict]:
        """Given parsed entries, HDEL stale ones (and any corrupt fields
        reported by ``_read_all_entries``). Returns survivors."""

        now = int(time.time())
        cutoff = now - PRESENCE_STALE_AFTER_SECONDS
        to_delete: list[str] = list(corrupt_fields or [])
        survivors: dict[str, dict] = {}
        for web_socket_id, data in entries.items():
            last_seen = data.get("last_seen", 0) if isinstance(data, dict) else 0
            if last_seen < cutoff:
                to_delete.append(web_socket_id)
                logger.debug(
                    "stale prune group={} session={} age={}s",
                    group_name,
                    web_socket_id,
                    now - last_seen,
                )
            else:
                survivors[web_socket_id] = data
        if to_delete:
            redis = _get_async_redis()
            await redis.hdel(self._key(group_name), *to_delete)
        return survivors

    async def _upsert(self, group_name: str, focus: Optional[dict] = None) -> None:
        redis = _get_async_redis()
        key = self._key(group_name)
        entry = json.dumps(
            {
                "user_id": self.user_id,
                "focus": focus,
                "last_seen": int(time.time()),
            }
        )
        async with redis.pipeline() as pipe:
            pipe.hset(key, self.web_socket_id, entry)
            pipe.expire(key, PRESENCE_STALE_AFTER_SECONDS * 4)
            await pipe.execute()

    @staticmethod
    def _format_snapshot(
        entries: dict[str, dict], exclude_web_socket_id: Optional[str] = None
    ) -> list[PresenceSnapshotEntry]:
        return [
            PresenceSnapshotEntry(
                user_id=data.get("user_id"),
                web_socket_id=ws_id,
                focus=data.get("focus"),
            )
            for ws_id, data in entries.items()
            if ws_id != exclude_web_socket_id
        ]

    async def add_presence(
        self,
        group_name: str,
        focus: Optional[dict] = None,
        previous_web_socket_id: Optional[str] = None,
    ) -> list[PresenceSnapshotEntry]:
        """
        Prune stale entries, purge previous session if reconnecting, upsert
        this connection's entry, and return the snapshot of *other* present
        sessions (this connection is excluded).
        """

        entries, corrupt = await self._read_all_entries(group_name)
        survivors = await self._prune_stale(group_name, entries, corrupt)

        if previous_web_socket_id and previous_web_socket_id in survivors:
            redis = _get_async_redis()
            await redis.hdel(self._key(group_name), previous_web_socket_id)
            del survivors[previous_web_socket_id]

        await self._upsert(group_name, focus)

        return self._format_snapshot(
            survivors, exclude_web_socket_id=self.web_socket_id
        )

    async def update_focus(self, group_name: str, focus: Optional[dict]) -> None:
        await self._upsert(group_name, focus)

    async def remove_presence(self, group_name: str) -> None:
        """Remove this connection's entry. Idempotent."""

        redis = _get_async_redis()
        await redis.hdel(self._key(group_name), self.web_socket_id)

    async def get_snapshot(
        self, group_name: str, exclude_web_socket_id: Optional[str] = None
    ) -> list[PresenceSnapshotEntry]:
        """Read-only snapshot of all current entries. No prune, no upsert."""

        entries, _corrupt = await self._read_all_entries(group_name)
        return self._format_snapshot(
            entries, exclude_web_socket_id=exclude_web_socket_id
        )

    async def _broadcast(self, group_name: str, payload: dict) -> None:
        """Ephemeral — no record_realtime_event. Client gets fresh snapshot on reconnect."""

        await send_message_to_channel_group(
            self.channel_layer,
            group_name,
            {
                "type": "broadcast_to_group",
                "payload": payload,
                "ignore_web_socket_id": self.web_socket_id,
            },
        )

    async def broadcast_join(self, group_name: str) -> None:
        await self._broadcast(
            group_name,
            {
                "type": "presence.join",
                "channel": group_name,
                "user_id": self.user_id,
                "web_socket_id": self.web_socket_id,
            },
        )

    async def broadcast_leave(self, group_name: str) -> None:
        await self._broadcast(
            group_name,
            {
                "type": "presence.leave",
                "channel": group_name,
                "user_id": self.user_id,
                "web_socket_id": self.web_socket_id,
            },
        )

    async def broadcast_focus(self, group_name: str, focus: Optional[dict]) -> None:
        await self._broadcast(
            group_name,
            {
                "type": "presence.focus",
                "channel": group_name,
                "user_id": self.user_id,
                "web_socket_id": self.web_socket_id,
                "focus": focus,
            },
        )
