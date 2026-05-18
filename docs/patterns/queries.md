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
loop that issues one or more queries per iteration. At one hundred rows it's
invisible. At a hundred thousand it's a production incident.

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
   `backend/src/baserow/contrib/database/table/handler.py`
   (`table_qs.only("id").iterator(1000)`).
3. **Bulk writes.** Collect everything to insert or update in a list and call
   `Model.objects.bulk_create(objs, batch_size=100)` or
   `Model.objects.bulk_update(objs, ["col"], batch_size=100)` after the
   loop. Never `.save()` in a loop.
4. **Chunked bulk writes for very large arrays.** `baserow.core.utils.grouper`
   (`from baserow.core.utils import grouper`) splits an iterable into
   chunks of N items. Use it when the input list is too large to bulk-write
   in a single call (memory, lock duration). See
   `backend/src/baserow/contrib/database/migrations/0081_batch_webhooks.py`
   for `grouper(...)` plus `bulk_create(batch_size=100)`.
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

- `backend/src/baserow/core/handler.py` — fetching `Settings` with a related
  co-branding logo image (`select_related("co_branding_logo")`) avoids a
  follow-up query on access.
- `backend/src/baserow/core/handler.py` — `WorkspaceUser` with two
  chained `.select_related("user").select_related("user__profile")` calls.
  One query, two joined tables.

Don't chain deeper than 2-3 levels — Postgres is happy, but the SQL gets
unwieldy and the result rows get wide.

## `prefetch_related` — reverse FK and M2M

Use when each result needs a collection.

Simple cases:

- `backend/src/baserow/core/handler.py` — `prefetch_related("workspaceuser_set",
  "template_set")` batches two reverse-FK queries for workspace listings.
- `backend/src/baserow/contrib/database/application_types.py` —
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

The same pattern appears in `backend/src/baserow/core/handler.py`. The
`Prefetch()` object lets you chain further optimisations into the prefetched
relation — without it, the prefetch fetches all columns naively.

A more advanced shape that filters fields and adds annotations is in
`backend/src/baserow/contrib/database/search_types.py`.

## `specific()` and `specific_iterator()` — polymorphic models

Baserow uses Django's content-type framework to make `Application`, `Field`,
and several other models polymorphic. Querying the base model returns base
instances; you usually want the concrete subclass.

For a single instance: `application.specific` resolves to a `Database` (or
whatever concrete type).

For many instances: never call `.specific` in a loop — that's N queries.
Instead use `specific_iterator()` (`backend/src/baserow/core/db.py`), which
groups by content type and fetches each subclass in a single query per type.

Example call sites:

- `backend/src/baserow/core/service.py` — `get_application` uses
  `specific_iterator()` with the `per_content_type_queryset_hook` parameter
  to attach prefetches per subclass.
- `enterprise/backend/src/baserow_enterprise/ws/restricted_view/fields/signals.py`
  — a more elaborate example where each subclass gets a different prefetch.

If you find yourself doing `for x in qs: x.specific.something`, replace with
`for x in specific_iterator(qs): x.something`.

## Column trimming — `only`, `defer`, `values_list`

When you don't need full rows:

- **`.only("id")`** — load only specific columns, paired with `.iterator()`
  for streaming large querysets.
  `backend/src/baserow/contrib/database/table/handler.py`:
  `table_qs.only("id").iterator(1000)` for bulk table processing.
- **`.defer("password")`** — exclude one or more columns from the load.
  `backend/src/baserow/api/authentication.py` uses this to keep passwords out of
  the user cache.
- **`.values_list("name", flat=True)`** — return tuples / scalars, not
  models. `backend/src/baserow/core/handler.py` has bulk name-only lookups.

These matter most when:

- You're iterating thousands of rows for a backfill or migration.
- You're caching, and the cached payload size matters.
- You want to avoid loading rarely-accessed binary blobs.

> **`.values()` and `.values_list()` always hit the database.** They issue a
> fresh query even when the queryset has already been evaluated. If you
> already have the model instances in memory (`objs = list(qs)`) and you also
> need their ids or one of their fields, iterate the list — don't run a
> second query.
>
> ```python
> # BAD — two queries against the same rows
> objs = list(MyModel.objects.filter(...))
> ids = MyModel.objects.filter(...).values_list("id", flat=True)
>
> # GOOD — one query, then a Python loop
> objs = list(MyModel.objects.filter(...))
> ids = [o.id for o in objs]
> ```

## Bulk writes

For ≥10 writes, never loop `.save()`.

- **`bulk_create(batch_size=100)`** — `backend/src/baserow/core/apps.py` registers
  all operation types in one go (`ignore_conflicts=True` skips duplicates).
- **`bulk_update(objs, ["field"], batch_size=100)`** —
  `backend/src/baserow/core/handler.py` updates the `order` field for many imported
  applications at once.
- **`update_or_create(defaults={...}, ...)`** — idempotent upsert.
  `backend/src/baserow/core/handler.py` for workspace invitations.

Choose `batch_size` so each batch fits in a reasonable query (100-500 is
usually right). Larger batches reduce round-trips but increase memory and
lock duration.

## Counting rows — beware big tables

`QuerySet.count()` runs `SELECT COUNT(*) FROM ...` which, on PostgreSQL, has
to scan every matching row even with an index. On a small table it's free;
on a multi-million-row table it can take seconds and block the request thread.
A `.count()` call in a request hot path, on a list endpoint over a large
user table, can grind the API to a halt.

Be deliberate about where you call `.count()`:

- Avoid it in list endpoints when the caller doesn't actually need an exact
  total (paginated UIs often only need "is there a next page?").
- Avoid it inside loops or per-request middleware.
- If you're guarding a code path with `if qs.count() > 0:`, use
  `qs.exists()` — it stops at the first match.

When you need a count on a potentially large table, prefer
`baserow.core.db.get_approximate_row_count(queryset)`. It runs
`EXPLAIN (FORMAT JSON)` to read PostgreSQL's planner estimate (cheap — uses
table statistics from `ANALYZE`, no scan), and:

- If the estimate is below `APPROXIMATE_COUNT_THRESHOLD` (50 000), it falls
  back to an exact `COUNT(*)` since the scan is cheap at that size and the
  planner estimate is unreliable on small sets.
- Otherwise it returns the estimate as-is — fast, approximate.

Defined in `backend/src/baserow/core/db.py`. Use it when you'd rather have a fast
ballpark on big tables than an accurate-but-slow number.

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

`backend/src/baserow/core/handler.py` (`get_workspace_for_update`) is the canonical
example. Always pair with `transaction.atomic()`. See
[postgresql-locks.md](../technical/postgresql-locks.md) for the broader lock
strategy.

## N+1 hotspots — fix and guard

When fixing an N+1, add a query-count test as the regression guard. The
enterprise tests in
`enterprise/backend/tests/baserow_enterprise_tests/api/admin/data_scanner/test_data_scanner_views.py`
show the pattern: capture queries for a small dataset, repeat with a larger
dataset, and assert the counts are equal. The assertion fails if the count
grows with dataset size — exactly what an N+1 would do.

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
5. **Trim columns** if you're processing thousands of rows or caching. Don't
   call `.values()` / `.values_list()` to re-fetch fields from objects you've
   already loaded — loop the in-memory list instead.
6. **Bulk-write** anything ≥ 10 mutations. Use `grouper` to chunk very large
   batches.
7. **Lock** rows you'll update if concurrent mutation is possible.
8. **Don't reach for `.count()`** on a potentially large table in a request
   path — use `qs.exists()` for presence checks, or
   `get_approximate_row_count(qs)` (`backend/src/baserow/core/db.py`) when a ballpark
   is good enough.
9. **Add a query-count test** on the hot path you cared enough to optimise.
10. **Drop to raw SQL or a CTE** for set-based work the ORM can't express
    efficiently — but accept that signals, cachalot, and search reindex won't
    fire.

## Related

- [Architectural patterns](architecture.md) — where handlers fit.
- [Creating features](creating-features.md) — the broader how-to for writing a
  view + action + handler + model.
- [PostgreSQL locks](../technical/postgresql-locks.md).
- [Caching](../technical/caching.md) — `cachalot` enablement for user-table
  queries.
