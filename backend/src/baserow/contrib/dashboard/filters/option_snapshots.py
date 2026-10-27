import hashlib
import json
import re
import time
from uuid import uuid4

from django.core import signing
from django.core.cache import cache

from django_redis import get_redis_connection

from baserow.contrib.dashboard.filters.exceptions import (
    DashboardFilterOptionsExpired,
    DashboardFilterOptionsTooLarge,
)
from baserow.core.formula.validator import ensure_string

MAX_SNAPSHOT_VALUES = 100_000
MAX_SNAPSHOT_BYTES = 10 * 1024 * 1024

PUBLISH_SNAPSHOT = """
local count = tonumber(ARGV[1])
if redis.call('ZCARD', KEYS[1]) ~= count then
    return 0
end
if count > 0 then
    if redis.call('ZCARD', KEYS[2]) ~= count then
        redis.call('RENAME', KEYS[1], KEYS[2])
    end
    redis.call('EXPIRE', KEYS[2], ARGV[2])
end
redis.call('SET', KEYS[3], ARGV[3], 'EX', ARGV[2])
redis.call('DEL', KEYS[1])
return 1
"""


class DashboardFilterOptionsSnapshot:
    """
    Share immutable option payloads while giving each reader its own expiry.

    Each snapshot is limited to MAX_SNAPSHOT_VALUES and MAX_SNAPSHOT_BYTES and
    readers expire after one hour. Refreshes resolve choices again and reuse an
    identical payload without extending an older reader's signed deadline.
    """

    lifetime = 60 * 60
    batch_size = 100
    batch_bytes = 64 * 1024

    def __init__(self, user, configuration):
        fingerprint = hashlib.sha256(
            json.dumps(configuration.formula_value, sort_keys=True).encode()
        ).hexdigest()
        self.prefix = cache.make_key(
            f"dashboard-filter-options:{user.pk}:{configuration.pk}:{fingerprint}"
        )
        self.salt = self.prefix
        self.redis = get_redis_connection("default")

    def create(self, value_factory, table_ids):
        key = self.key(uuid4().hex)
        digest = hashlib.sha256()
        batch = {}
        batch_bytes = total_bytes = count = 0
        values = None
        try:
            values = value_factory()
            for index, raw_value in enumerate(values):
                value = ensure_string(raw_value)
                if not value.strip() or value in batch:
                    continue
                size = len(value.encode())
                if size > MAX_SNAPSHOT_BYTES:
                    raise DashboardFilterOptionsTooLarge()
                batch[value] = (index, size)
                batch_bytes += size
                if len(batch) >= self.batch_size or batch_bytes >= self.batch_bytes:
                    count, total_bytes = self._write_batch(
                        key, batch, count, total_bytes, digest
                    )
                    batch.clear()
                    batch_bytes = 0
            if batch:
                count, total_bytes = self._write_batch(
                    key, batch, count, total_bytes, digest
                )
            metadata = {"table_ids": sorted(table_ids), "count": count}
            serialized_metadata = json.dumps(metadata, sort_keys=True)
            digest.update(serialized_metadata.encode())
            snapshot_id = digest.hexdigest()
            snapshot_key = self.key(snapshot_id)
            expires_at = int(time.time()) + self.lifetime
            # Publication, reuse and TTL changes must be atomic with concurrent
            # refreshes. Reject a staging payload evicted during construction.
            published = self.redis.eval(
                PUBLISH_SNAPSHOT,
                3,
                key,
                snapshot_key,
                f"{snapshot_key}:metadata",
                count,
                self.lifetime,
                serialized_metadata,
            )
            if not published:
                raise DashboardFilterOptionsExpired()
        except Exception:
            self.redis.delete(key)
            raise
        finally:
            # Close database iterators before an API error rolls back its transaction.
            close = getattr(values, "close", None)
            if close is not None:
                close()
        return self.cursor(snapshot_id, 0, expires_at)

    def _write_batch(self, key, values, count, total_bytes, digest):
        with self.redis.pipeline() as pipeline:
            for value, (index, _) in values.items():
                pipeline.zadd(key, {value: index}, nx=True)
            pipeline.expire(key, self.lifetime)
            *added, _ = pipeline.execute()
        count += sum(added)
        total_bytes += sum(
            size for (_, size), was_added in zip(values.values(), added) if was_added
        )
        if count > MAX_SNAPSHOT_VALUES or total_bytes > MAX_SNAPSHOT_BYTES:
            raise DashboardFilterOptionsTooLarge()
        for (value, (_, size)), was_added in zip(values.items(), added):
            if was_added:
                # Length prefixes preserve value boundaries; only first occurrences
                # contribute, so duplicate input rows still share the same payload.
                digest.update(size.to_bytes(8, "big"))
                digest.update(value.encode())
        return count, total_bytes

    def key(self, snapshot_id):
        return f"{self.prefix}:{snapshot_id}"

    def cursor(self, snapshot_id, offset, expires_at):
        return signing.Signer(salt=self.salt).sign_object(
            [snapshot_id, offset, expires_at]
        )

    def page(self, cursor, *, limit, selected, validate_tables):
        try:
            snapshot_id, offset, expires_at = signing.Signer(
                salt=self.salt
            ).unsign_object(cursor)
            if (
                not isinstance(snapshot_id, str)
                or not re.fullmatch(r"[0-9a-f]{64}", snapshot_id)
                or type(offset) is not int
                or offset < 0
                or type(expires_at) is not int
                or expires_at <= time.time()
            ):
                raise ValueError("Invalid snapshot cursor")
        except (signing.BadSignature, TypeError, ValueError) as exc:
            raise DashboardFilterOptionsExpired() from exc
        key = self.key(snapshot_id)
        metadata = self.redis.get(f"{key}:metadata")
        if metadata is None:
            raise DashboardFilterOptionsExpired()
        metadata = json.loads(metadata)
        validate_tables(metadata["table_ids"])
        selected = list(dict.fromkeys(selected))
        with self.redis.pipeline() as pipeline:
            pipeline.zcard(key)
            pipeline.zrange(key, offset, offset + limit)
            for value in selected:
                pipeline.zscore(key, value)
            count, values, *scores = pipeline.execute()
        # Eviction or expiration must not turn a partial snapshot into an empty page.
        if count != metadata["count"]:
            raise DashboardFilterOptionsExpired()
        return {
            "results": [value.decode() for value in values[:limit]],
            "next": self.cursor(snapshot_id, offset + limit, expires_at)
            if len(values) > limit
            else None,
            "snapshot": self.cursor(snapshot_id, 0, expires_at),
            "available": [
                value for value, score in zip(selected, scores) if score is not None
            ],
        }
