# Query patterns

This page collects the ORM idioms you'll need when writing handlers and
services in Baserow. The goal is to make N+1 the exception and to surface the
patterns the codebase actually uses, with concrete locations to read for
context.

Rules of thumb up front:

- For foreign keys you'll dereference: **`select_related`**.
- For reverse foreign keys or many-to-many: **`prefetch_related`**, with a
  `Prefetch()` object if the prefetched set needs filtering or extra joins.
- For polymorphic base models (`Application`, `Field`, etc.): **`specific()`**
  or **`specific_iterator()`** to fetch concrete subclass instances without
  N+1.
- For ≥10 writes: **`bulk_create` / `bulk_update`** with a `batch_size`.
- Don't trust correctness by inspection — add query-count tests on hot paths.

## The most important rule: never query inside a loop

If you remember nothing else from this page, remember this. The single most
common performance bug in this codebase — and most Django codebases — is a
loop that issues one query per iteration. At one hundred rows it's invisible.
At a hundred thousand it's a production incident.

Before writing `for x in something:`, ask: *does the body do any of these
forbidden things?*

- `.get(...)`, `.filter(...)`, `.first()` against the ORM.
- Touching a foreign key or reverse-FK attribute that wasn't prefetched
  (this issues a query lazily).
- Calling `.specific` (one query per content type if not batched).
- `.save()` (one INSERT or UPDATE per call).

If yes, restructure as one of:

1. **Prefetch outside the loop.** `select_related` for FKs you'll dereference,
   `prefetch_related` (with a `Prefetch()` object when you need filtering or
   nested optimisation) for reverse FKs and M2Ms. The loop body should never
   issue follow-up queries.
2. **Iterator for one-shot reads.** When you'll touch each row exactly once
   and the result set is large, `.iterator(chunk_size=N)` streams rows from
   the database instead of loading them all into memory. Combine with
   `.only(...)` to trim columns. Real example:
   `baserow/contrib/database/table/handler.py:208`
   (`table_qs.only("id").iterator(1000)`).
3. **Bulk writes.** Collect everything to insert or update in a list and call
   `Model.objects.bulk_create(objs, batch_size=100)` or
   `Model.objects.bulk_update(objs, ["col"], batch_size=100)` after the
   loop. Never `.save()` in a loop.
4. **Chunked bulk writes for very large arrays.** `baserow.core.utils.grouper`
   (`from baserow.core.utils import grouper`) splits an iterable into
   chunks of N items. Use it when the input list is too large to bulk-write
   in a single call (memory, lock duration). The migration in
   `baserow/contrib/database/migrations/0081_batch_webhooks.py` shows this
   in anger: `grouper(...)` plus `bulk_create(batch_size=100)`.
5. **Drop to SQL or a CTE.** When the work is fundamentally set-based —
   updating one column based on another across millions of rows, computing
   aggregates the ORM can't express efficiently — write the query. Use
   `connection.cursor()` or a `RawSQL` / `RunSQL` in a migration. CTEs (via
   `django-cte` or hand-rolled `WITH ... AS (...)`) handle the "update X
   from a derived set" shape without a Python loop at all. This is a
   precision tool: it skips signals, cachalot invalidation, and search
   reindex, so use it deliberately.

`groupby` from `itertools` (or `django.db.models` aggregation) is the right
tool when you want to roll up data; `grouper` is for batching writes. Don't
confuse them.

## `select_related` — single-query FK joins

Use when you'll access an FK attribute on each row in the result.

Real examples:

- `baserow/core/handler.py:171` — fetching `Settings` with a related
  co-branding logo image (`select_related("co_branding_logo")`) avoids a
  follow-up query on access.
- `baserow/core/handler.py:600-602` — `WorkspaceUser` with chained
  `select_related("user", "user__profile")`. One query, two joined tables.

Don't chain deeper than 2-3 levels — Postgres is happy, but the SQL gets
unwieldy and the result rows get wide.

## `prefetch_related` — reverse FK and M2M

Use when each result needs a collection.

Simple cases:

- `baserow/core/handler.py:564` — `prefetch_related("workspaceuser_set",
  "template_set")` batches two reverse-FK queries for workspace listings.
- `baserow/contrib/database/application_types.py:90` —
  `prefetch_related("field_set")` on a database application, used during
  serialisation.

With a custom queryset via `Prefetch()`:

```python
from django.db.models import Prefetch

workspaceusers_with_user_and_profile = (
    WorkspaceUser.objects.select_related("user", "user__profile")
)
workspaces = Workspace.objects.prefetch_related(
    Prefetch("workspaceuser_set", queryset=workspaceusers_with_user_and_profile),
)
```

The above pattern lives in `baserow/core/handler.py:606-609`. The
`Prefetch()` object lets you chain further optimisations into the prefetched
relation — without it, the prefetch fetches all columns naively.

A more advanced shape that filters fields and adds annotations is in
`baserow/contrib/database/search_types.py:274`.

## `specific()` and `specific_iterator()` — polymorphic models

Baserow uses Django's content-type framework to make `Application`, `Field`,
and several other models polymorphic. Querying the base model returns base
instances; you usually want the concrete subclass.

For a single instance: `application.specific` resolves to a `Database` (or
whatever concrete type).

For many instances: never call `.specific` in a loop — that's N queries.
Instead use `specific_iterator()` (`baserow/core/db.py:118-149`), which
groups by content type and fetches each subclass in a single query per type.

Example call sites:

- `baserow/core/service.py:137-143` — `get_application` uses
  `specific_iterator()` with the `per_content_type_queryset_hook` parameter
  to attach prefetches per subclass.
- `enterprise/.../restricted_view/fields/signals.py:31-34` — a more elaborate
  example where each subclass gets a different prefetch.

If you find yourself doing `for x in qs: x.specific.something`, replace with
`for x in specific_iterator(qs): x.something`.

## Column trimming — `only`, `defer`, `values_list`

When you don't need full rows:

- **`.only("id")`** — load only specific columns, paired with `.iterator()`
  for streaming large querysets.
  `baserow/contrib/database/table/handler.py:208`:
  `table_qs.only("id").iterator(1000)` for bulk table processing.
- **`.defer("password")`** — exclude one or more columns from the load.
  `baserow/api/authentication.py:36-38` uses this to keep passwords out of
  the user cache.
- **`.values_list("name", flat=True)`** — return tuples / scalars, not
  models. `baserow/core/handler.py:1458` for bulk name-only lookups.

These matter most when:

- You're iterating thousands of rows for a backfill or migration.
- You're caching, and the cached payload size matters.
- You want to avoid loading rarely-accessed binary blobs.

## Bulk writes

For ≥10 writes, never loop `.save()`.

- **`bulk_create(batch_size=100)`** — `baserow/core/apps.py:618-621` registers
  all operation types in one go (`ignore_conflicts=True` skips duplicates).
- **`bulk_update(objs, ["field"], batch_size=100)`** —
  `baserow/core/handler.py:1795` updates the `order` field for many imported
  applications at once.
- **`update_or_create(defaults={...}, ...)`** — idempotent upsert.
  `baserow/core/handler.py:1133-1140` for workspace invitations.

Choose `batch_size` so each batch fits in a reasonable query (100-500 is
usually right). Larger batches reduce round-trips but increase memory and
lock duration.

## Pessimistic locking — `select_for_update`

When the next operation depends on the row's current value and concurrent
mutation is possible (rename, delete, transfer), lock the row:

```python
workspace = (
    Workspace.objects
    .select_for_update(of=("self",))
    .get(pk=workspace_id)
)
```

`baserow/core/handler.py:531` (`get_workspace_for_update`) is the canonical
example. Always pair with `transaction.atomic()`. See
[postgresql-locks.md](../technical/postgresql-locks.md) for the broader lock
strategy.

## N+1 hotspots — fix and guard

When fixing an N+1, add a query-count test as the regression guard. The
enterprise tests in
`enterprise/backend/tests/.../data_scanner/test_data_scanner_views.py:141-145`
show the pattern: `@override_settings(DEBUG=True)` plus
`assert len(connection.queries) <= N`. The assertion fails if the count grows
with dataset size — exactly what an N+1 would do.

Comments in the codebase calling out N+1 fixes are searchable; look for
`# N+1` or commit messages mentioning N+1.

## Cheat sheet — writing a new handler method

1. **No queries inside loops.** Prefetch, iterate, bulk-write — see the
   first section of this page.
2. **Identify every FK you'll dereference.** Add `select_related` for them.
3. **Identify every collection you'll iterate.** Add `prefetch_related` (or
   a `Prefetch()` object if you need further optimisation).
4. **If the model is polymorphic (`Application`, `Field`, etc.) and you'll
   call `.specific`,** use `specific_iterator` instead of a loop.
5. **Trim columns** if you're processing thousands of rows or caching.
6. **Bulk-write** anything ≥ 10 mutations. Use `grouper` to chunk very large
   batches.
7. **Lock** rows you'll update if concurrent mutation is possible.
8. **Add a query-count test** on the hot path you cared enough to optimise.
9. **Drop to raw SQL or a CTE** for set-based work the ORM can't express
   efficiently — but accept that signals, cachalot, and search reindex won't
   fire.

## Related

- [Architectural patterns](architecture.md) — where handlers fit.
- [Creating features](creating-features.md) — the broader how-to for writing a
  view + action + handler + model.
- [PostgreSQL locks](../technical/postgresql-locks.md).
- [Caching](../technical/caching.md) — `cachalot` enablement for user-table
  queries.
