# Caching

Baserow caches at several levels: per-request in-process, distributed Redis,
and ad-hoc `lru_cache`/`cached_property` decorators in hot paths. This page
is the map. If you're touching anything performance-sensitive, know the
layer you're in and what invalidates it.

## At a glance

| Layer | Backend | Scope | TTL | Invalidation |
|---|---|---|---|---|
| `local_cache` | `asgiref.Local` (in-process) | One request / task | Auto, on exit | Auto via `LocalCacheMiddleware`; explicit `.delete(key)` |
| `global_cache` | Django cache (Redis) | Cross-request | Per call; defaults short | Versioned counter; `.invalidate()` |
| `generated-models` cache | Dedicated Django cache (Redis) | Cross-request | None | `Table.version` UUID change |
| User & Settings cache | Django cache | Cross-request | `BASEROW_CACHE_TTL_SECONDS` | `post_save` signals |
| Job progress cache | Django cache (Redis) | Cross-request | While job runs | On job completion |
| `lru_cache` / `cached_property` | In-process | Worker lifetime / object lifetime | None | Worker restart / object disposal |

The two you should know cold: **`local_cache`** (request-scoped) and
**`global_cache`** (Redis, versioned). Most of the rest are special-purpose.

## Framework-layer caches

### `local_cache` — per-request in-process

`baserow.core.cache.local_cache`. Backed by `asgiref.local.Local`, so it's
thread- and async-safe.

```python
from baserow.core.cache import local_cache

value = local_cache.get(
    f"workspace_user_{workspace.id}_{user.id}",
    default=lambda: fetch_workspace_user(workspace, user),
)
```

`LocalCacheMiddleware` (and analogous wrappers for Celery tasks and async
contexts) clears the cache at the boundary so values never leak across
requests.

Use it for **anything you'd look up twice in the same request**: permission
checks, role assignments, repeated workspace lookups, dynamic model lookups,
etc. It's strictly free — no Redis round-trip — so the bar for using it is
low.

The `delete(key)` method supports `*` wildcards for invalidating families
(e.g. `local_cache.delete("role_assignments_*")`).

### `global_cache` — versioned Redis cache

`baserow.core.cache.global_cache`. Wraps the Django cache backend
(`django.core.cache.cache`) with two patterns:

1. **Versioned keys.** Each cached entry carries a version number; calling
   `.invalidate(key)` increments that counter so all readers atomically see a
   miss without you having to know every key that should be flushed.
2. **Distributed locks.** When a cache miss occurs, the populator runs under a
   short-lived Redis lock to prevent thundering-herd recompute.

```python
data = global_cache.get(
    "expensive_thing",
    default=lambda: compute_expensive_thing(),
    timeout=300,
    invalidate_key="expensive_thing_family",
)

global_cache.invalidate("expensive_thing_family")
```

Use it for **expensive cross-request computations** with clear invalidation
points: rendered settings, user metadata, derived structures recomputed
periodically.

### Django cache backends overview

`baserow.config.settings.base` defines several Django cache "names":

- `default` — main Redis cache. Used by `global_cache`, sessions, etc.
- `generated-models` — separate cache for `Table.get_model()` `field_attrs`
  (see [dynamic models](dynamic-models.md)).

Splitting caches by name keeps flushes targeted: clearing one cache doesn't
clear the others.

## Application-layer caches

### Generated model `field_attrs` cache

Covered in detail in [dynamic models](dynamic-models.md). Two-layer
(`local_cache` + `generated-models` Redis cache), versioned by
`Table.version` UUID, invalidated by every field change.

### User & Settings caches

`baserow.core.user.cache` and the singleton `Settings` cache. Cache full User
ORM objects (with `UserProfile` preloaded) and the global `Settings` row.

TTL controlled by `BASEROW_CACHE_TTL_SECONDS` (env). Default `0` in dev (off);
production sets a small TTL.

Invalidated by `post_save` signal handlers on `User`, `UserProfile` and
`Settings`. There's an explicit `invalidate_cached_user(user_id)` helper for
flows that need it.

### Job progress cache

`baserow.core.jobs.cache`. Holds `progress_percentage` and `state` for
in-flight `Job` rows. Necessary because DB transaction isolation otherwise
hides progress updates from other workers and the API. The job model uses
`.get_from_cached_value_or_from_self()` to prefer the cache when available
and fall back to the DB row.

### Role assignment cache (enterprise)

`enterprise/backend/.../role/handler.py`. Caches role lookups and role
assignments per actor/scope using `local_cache`. Decorator
`@clear_roles_from_local_cache()` clears the cache after role mutations.

Per-class in-memory cache for `Role` objects (used at module level — these
are essentially immutable for the worker's lifetime).

### Registry lookups

`baserow.core.registry`. Several registry methods are wrapped in
`@lru_cache`, e.g. `get_for_class()` for content-type-keyed lookups. These
are unbounded process-level caches; registry contents don't change at
runtime, so the cache is essentially permanent.

### Search index existence

`baserow.contrib.database.search.handler._workspace_search_table_exists` is
wrapped in `@lru_cache(maxsize=1024)`. Cached for the worker's lifetime.
Acceptable because workspace search tables are created once and effectively
never dropped during a workspace's lifetime.

### `cached_property` and friends

Used liberally on models and request-scoped objects:

- `Field.get_field_objects()`.
- `FieldRule.filter_type()`.
- `Page.get_theme()`.
- Builder `*DispatchContext` properties.

These cache for the lifetime of the object instance and need no explicit
invalidation — discarding the instance discards the cache.

## Minor / specialised caches

- **Celery singleton locks** (`baserow.celery_singleton_backend`) — Redis-
  backed locks preventing duplicate task runs.
- **Auto-index lock flags** for search auto-indexing.

## Things every dev should know

1. **`local_cache` is essentially free; use it.** If you're looking up the
   same thing twice in a request (permissions, workspace membership, dynamic
   model), wrap it.
2. **Versioned caches don't need surgical invalidation.** When you change
   something cached by `global_cache` or the `generated-models` cache, you
   roll the version once and every reader sees a miss on next access.
   You do not need to know every key in the family.
3. **`BASEROW_VERSION` is part of several cache keys.** A Baserow upgrade
   gives you a free flush. You can rely on this for cross-release schema
   changes that didn't get an explicit invalidation.
4. **`lru_cache` lives until the worker restarts.** Don't use it for anything
   that changes at runtime. Don't use it on functions with `self`, ever
   (silent memory leaks).
5. **Cache invalidation can run under writer locks.** Several mutations
   invalidate cached state while holding row or table locks (e.g. the
   `generated-models` version bump runs inside the field-handler
   transaction). Cheap invalidations are fine; doing expensive work inside
   `invalidate()` callbacks extends the lock window. See
   [PostgreSQL locking](postgresql-locks.md) for the lock side of this.

## Common mistakes

1. **Forgetting that `local_cache` is per-request.** If you cache a value at
   module import time using `local_cache`, you're not caching anything —
   it'll be empty on the first request that hits the code.
2. **Leaking context across cache keys.** Don't cache user-scoped data under
   a workspace-only key; it'll cross-leak between users sharing a workspace.
   Always include the smallest identifier that defines the answer (`user_id`,
   not just `workspace_id`).
3. **Relying on TTL as the invalidation strategy.** TTL is a safety net.
   Mutations should explicitly invalidate. Otherwise you race with the TTL
   and users see stale data unpredictably.

## Related

- [Dynamic models](dynamic-models.md) — the most prominent application of the
  generated-models cache.
- [Workspace search guide](workspace-search.md) — search index `lru_cache`.
- [Architectural patterns](../patterns/architecture.md) — where caching fits
  relative to handlers and services.
