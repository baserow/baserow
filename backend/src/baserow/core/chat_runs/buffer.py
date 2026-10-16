"""Bounded, temporary output. Redis is never the authority for run lifecycle.

The namespace deliberately does not contain Baserow's release/cache version.
Only Redis 6.2 commands are used. Every follower reads the whole stream, so
consumer groups are inappropriate here.
"""

import asyncio
import json
import re
from contextlib import suppress
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4
from weakref import WeakKeyDictionary

from django.conf import settings

from redis.asyncio import BlockingConnectionPool, Redis, from_url

ACTIVE_TTL_SECONDS = 3600
FINISHED_TTL_SECONDS = 24 * 60 * 60
MAX_BUFFER_BYTES = 8 * 1024 * 1024
MAX_BUFFER_EVENTS = 10000
OPERATION_TIMEOUT_SECONDS = 1.0
READ_BLOCK_MILLISECONDS = 5000
FOLLOWER_POOL_CONNECTIONS = 128

_pools: WeakKeyDictionary = WeakKeyDictionary()
_read_pools: WeakKeyDictionary = WeakKeyDictionary()
_test_client: Redis | None = None
_CURSOR = re.compile(r"^([a-f0-9]{32}):([0-9]{1,20}-[0-9]{1,20})$")

# Keeping the entire prefix is intentional. Trimming a delta log would make a
# refreshed browser reconstruct the wrong answer. At the limit, disable replay
# explicitly instead. Both keys share a hash tag for Redis Cluster deployments.
_APPEND = """
local meta = KEYS[1]
local stream = KEYS[2]
local generation = redis.call('HGET', meta, 'generation')
if not generation then
    if ARGV[2] ~= '1' or redis.call('EXISTS', stream) == 1 then
        return {'unavailable', 'missing'}
    end
    generation = ARGV[1]
    redis.call('HSET', meta, 'generation', generation, 'state', 'ready',
               'bytes', 0, 'count', 0)
end
if ARGV[7] ~= '1' and generation ~= ARGV[1] then
    return {'unavailable', 'generation'}
end
if redis.call('HGET', meta, 'state') ~= 'ready' then
    return {'unavailable', 'limit'}
end
local first = redis.call('HGET', meta, 'first')
if first then
    local retained = redis.call('XRANGE', stream, '-', '+', 'COUNT', 1)
    if #retained == 0 or retained[1][1] ~= first then
        redis.call('HSET', meta, 'state', 'unavailable')
        return {'unavailable', 'prefix'}
    end
end
local payloads = cjson.decode(ARGV[3])
local bytes = tonumber(redis.call('HGET', meta, 'bytes'))
local count = tonumber(redis.call('HGET', meta, 'count'))
local extra = 0
for _, payload in ipairs(payloads) do extra = extra + string.len(payload) end
if bytes + extra > tonumber(ARGV[4]) or count + #payloads > tonumber(ARGV[5]) then
    redis.call('HSET', meta, 'state', 'limit')
    redis.call('EXPIRE', meta, ARGV[6])
    redis.call('EXPIRE', stream, ARGV[6])
    return {'unavailable', 'limit'}
end
local ids = {'ok', generation}
for _, payload in ipairs(payloads) do
    local id = redis.call('XADD', stream, '*', 'payload', payload)
    if not first then
        first = id
        redis.call('HSET', meta, 'first', first)
    end
    redis.call('HSET', meta, 'last', id)
    table.insert(ids, id)
end
redis.call('HSET', meta, 'bytes', bytes + extra, 'count', count + #payloads)
redis.call('EXPIRE', meta, ARGV[6])
redis.call('EXPIRE', stream, ARGV[6])
return ids
"""

_FINISH = """
if redis.call('HGET', KEYS[1], 'generation') == ARGV[1] then
    redis.call('EXPIRE', KEYS[1], ARGV[2])
    redis.call('EXPIRE', KEYS[2], ARGV[2])
end
return 1
"""

_INVALIDATE = """
local generation = redis.call('HGET', KEYS[1], 'generation')
if generation and (ARGV[2] == '1' or generation == ARGV[1]) then
    redis.call('HSET', KEYS[1], 'state', 'unavailable')
    redis.call('EXPIRE', KEYS[1], ARGV[3])
    redis.call('EXPIRE', KEYS[2], ARGV[3])
end
return 1
"""


class ReplayUnavailable(Exception):
    """A complete prefix or the requested generation is no longer available."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


@dataclass(frozen=True)
class BufferRead:
    events: list[dict[str, Any]]
    cursor: str | None
    generation: str
    high_water: str | None


def parse_cursor(cursor: str) -> tuple[str, str]:
    match = _CURSOR.fullmatch(cursor) if isinstance(cursor, str) else None
    if match is None:
        raise ValueError("Invalid chat run cursor")
    if any(int(part) > 2**64 - 1 for part in match.group(2).split("-")):
        raise ValueError("Invalid chat run cursor")
    return match.group(1), match.group(2)


validate_cursor = parse_cursor


def stream_id_key(stream_id: str) -> tuple[int, int]:
    return tuple(int(part) for part in stream_id.split("-"))


async def get_buffer_redis(*, blocking: bool = False) -> Redis:
    """Blocked followers cannot exhaust the writer/cache/lease connections."""

    if _test_client is not None:
        return _test_client
    pools = _read_pools if blocking else _pools
    loop = asyncio.get_running_loop()
    if loop not in pools:
        options = {
            "decode_responses": True,
            "socket_connect_timeout": OPERATION_TIMEOUT_SECONDS,
            "socket_timeout": (
                READ_BLOCK_MILLISECONDS / 1000 + OPERATION_TIMEOUT_SECONDS
                if blocking
                else OPERATION_TIMEOUT_SECONDS
            ),
        }
        if blocking:
            # Connect outside the pool's checkout lock so a cold cohort of
            # followers does not serialize every TCP/authentication handshake.
            pools[loop] = Redis.from_pool(
                BlockingConnectionPool.from_url(
                    settings.REDIS_URL,
                    max_connections=FOLLOWER_POOL_CONNECTIONS,
                    timeout=OPERATION_TIMEOUT_SECONDS,
                    **options,
                )
            )
        else:
            pools[loop] = from_url(settings.REDIS_URL, max_connections=16, **options)
    return pools[loop]


def set_buffer_redis(client: Redis | None) -> None:
    """Inject a fake/isolated Redis in tests, without touching other Redis users."""

    global _test_client
    _test_client = client


async def close_buffer_redis() -> None:
    """Release clients before a Celery/async_to_sync temporary loop is closed.

    HTTP followers share a server loop and retain its pools. Injected test clients
    are owned by their fixture, rather than by an individual publishing call.
    """

    loop = asyncio.get_running_loop()
    for pools in (_pools, _read_pools):
        client = pools.pop(loop, None)
        if client is not None:
            with suppress(Exception):
                async with asyncio.timeout(OPERATION_TIMEOUT_SECONDS):
                    await client.aclose()


class ChatRunBuffer:
    def __init__(self, run_id: UUID | str) -> None:
        run_id = UUID(str(run_id))
        self.meta_key = f"baserow:chat-runs:v1:{{{run_id}}}:meta"
        self.stream_key = f"baserow:chat-runs:v1:{{{run_id}}}:events"
        self.generation = uuid4().hex
        self._created = False

    async def append(
        self, events: list[tuple[str, dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        """Append once atomically. An ambiguous failure must never be retried.

        The journal stops publishing after an error: retrying a timed-out append
        could duplicate deltas, and recreating an evicted key could lose a prefix.
        The worker still owns its answer in memory and persists it at termination.
        """

        if not events:
            return []
        payloads = [
            json.dumps(
                {"kind": kind, "data": data}, allow_nan=False, separators=(",", ":")
            )
            for kind, data in events
        ]
        client = await get_buffer_redis()
        async with asyncio.timeout(OPERATION_TIMEOUT_SECONDS):
            result = await client.eval(
                _APPEND,
                2,
                self.meta_key,
                self.stream_key,
                self.generation,
                "1"
                if not self._created and events[0][0] in ("run.created", "run.started")
                else "0",
                json.dumps(payloads),
                MAX_BUFFER_BYTES,
                MAX_BUFFER_EVENTS,
                ACTIVE_TTL_SECONDS,
                "0" if self._created else "1",
            )
        # A subsequent call is never allowed to create a fresh prefix.
        self._created = True
        if result[0] != "ok":
            raise ReplayUnavailable(result[1])
        self.generation = result[1]
        return [
            {"kind": kind, "data": data, "cursor": f"{self.generation}:{stream_id}"}
            for (kind, data), stream_id in zip(events, result[2:], strict=True)
        ]

    async def _metadata(
        self, client: Redis, *, require_ready: bool = True
    ) -> dict[str, str]:
        async with asyncio.timeout(OPERATION_TIMEOUT_SECONDS):
            # Each follower needs these independent checks. Send them in one
            # round trip to stay within the same bounded read budget at scale.
            async with client.pipeline(transaction=False) as pipeline:
                pipeline.hgetall(self.meta_key)
                pipeline.xrange(self.stream_key, count=1)
                pipeline.xlen(self.stream_key)
                meta, first, length = await pipeline.execute()
        if not meta:
            raise ReplayUnavailable("missing")
        if require_ready and meta.get("state") != "ready":
            raise ReplayUnavailable(meta.get("state", "unavailable"))
        if (
            not first
            or first[0][0] != meta.get("first")
            or length < int(meta.get("count", 0))
        ):
            raise ReplayUnavailable("prefix")
        return meta

    async def read(
        self, cursor: str | None = None, *, block_ms: int = 0, count: int = 500
    ) -> BufferRead:
        """Replay and then wait using the same cursor, with no subscribe gap."""

        parsed = parse_cursor(cursor) if cursor else None
        client = await get_buffer_redis(blocking=True)
        meta = await self._metadata(client)
        generation = meta["generation"]
        stream_id = "0-0"
        if parsed:
            if parsed[0] != generation:
                raise ReplayUnavailable("generation")
            stream_id = parsed[1]
            if stream_id_key(stream_id) > stream_id_key(meta["last"]):
                raise ReplayUnavailable("cursor")
            # Reject fabricated/deleted IDs rather than silently skipping output.
            async with asyncio.timeout(OPERATION_TIMEOUT_SECONDS):
                exists = await client.xrange(
                    self.stream_key, min=stream_id, max=stream_id
                )
            if not exists:
                raise ReplayUnavailable("cursor")
        kwargs = {"block": min(block_ms, READ_BLOCK_MILLISECONDS)} if block_ms else {}
        async with asyncio.timeout(
            min(block_ms, READ_BLOCK_MILLISECONDS) / 1000 + OPERATION_TIMEOUT_SECONDS
        ):
            records = await client.xread(
                {self.stream_key: stream_id}, count=min(max(count, 1), 500), **kwargs
            )
        # Recheck after the blocking operation: eviction/recreation or unsafe
        # external trimming during XREAD must never turn a suffix into replay.
        after = await self._metadata(client)
        if after["generation"] != generation:
            raise ReplayUnavailable("generation")
        events = [
            {**json.loads(fields["payload"]), "cursor": f"{generation}:{event_id}"}
            for _, rows in records
            for event_id, fields in rows
        ]
        return BufferRead(
            events,
            events[-1]["cursor"] if events else cursor,
            generation,
            f"{generation}:{meta['last']}",
        )

    async def recover(self, cursor: str | None = None) -> list[dict[str, Any]] | None:
        """Read a complete prefix, bounded by a resume cursor when supplied.

        A baseline ends at its immutable cursor, so concurrent appends cannot
        invalidate it. Worker-loss recovery still requires the whole buffer.
        Both reads stay bounded and run outside SQL locks.
        """

        try:
            async with asyncio.timeout(OPERATION_TIMEOUT_SECONDS):
                client = await get_buffer_redis(blocking=True)
                meta = await self._metadata(client, require_ready=False)
                generation, position = parse_cursor(cursor) if cursor else (None, "+")
                if generation is not None and generation != meta["generation"]:
                    return None
                rows = await client.xrange(
                    self.stream_key, max=position, count=MAX_BUFFER_EVENTS + 1
                )
                after = await self._metadata(client, require_ready=False)
                if meta["generation"] != after["generation"]:
                    return None
                if (
                    len(rows) > MAX_BUFFER_EVENTS
                    or not rows
                    or rows[-1][0] != (position if cursor else after["last"])
                    or (not cursor and len(rows) != int(after["count"]))
                ):
                    return None
                return [
                    {
                        **json.loads(fields["payload"]),
                        "cursor": f"{meta['generation']}:{event_id}",
                    }
                    for event_id, fields in rows
                ]
        except Exception:
            # Missing Redis must never prevent an expired run from ending.
            return None

    async def finish(self) -> None:
        client = await get_buffer_redis()
        async with asyncio.timeout(OPERATION_TIMEOUT_SECONDS):
            await client.eval(
                _FINISH,
                2,
                self.meta_key,
                self.stream_key,
                self.generation,
                FINISHED_TTL_SECONDS,
            )

    async def invalidate(self) -> None:
        """Best-effort flag that this writer can no longer provide live replay.

        Never recreate deleted keys, or affect a replacement generation after
        this writer adopted its generation. The old prefix remains untrimmed.
        """

        client = await get_buffer_redis()
        async with asyncio.timeout(OPERATION_TIMEOUT_SECONDS):
            await client.eval(
                _INVALIDATE,
                2,
                self.meta_key,
                self.stream_key,
                self.generation,
                "0" if self._created else "1",
                ACTIVE_TTL_SECONDS,
            )
