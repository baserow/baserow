# Bulk writes

When you're inserting or updating many rows at once, individual
`.save()` calls or one-row-per-statement INSERTs are wrong by default.
Baserow uses three patterns repeatedly: `bulk_create`, `bulk_update`,
and `bulk_create(..., update_conflicts=True)` (the upsert form).

For the locking implications see
[PostgreSQL locks — bulk_create with on-conflict updates](../technical/postgresql-locks.md#bulk-create-upsert).
For chunked iteration on the read side see
[ORM and queries](queries.md).

## The three operations

### `bulk_create(items, batch_size=...)`

Plain bulk insert. One `INSERT INTO … VALUES (…), (…), …` statement
per `batch_size` rows.

```python
TableUsage.objects.bulk_create(
    [TableUsage(table=t, row_count=t.row_count) for t in tables],
    batch_size=500,
)
```

Use when:

- You're creating new rows that don't yet exist.
- You don't need the model's `pk` back immediately (Postgres can
  return PKs but other backends can't, and the assumption shouldn't
  bleed across backends).
- You don't need `save()` side effects (signals, custom `save`
  overrides — `bulk_create` skips them by design).

### `bulk_update(items, fields, batch_size=...)`

Updates a fixed set of columns across many already-loaded instances.

```python
fields_to_save = [...]   # in-memory Field instances with new values
Field.objects.bulk_update(fields_to_save, ["name", "order"], batch_size=200)
```

Use when:

- You already have the model instances in memory.
- You're changing the same set of columns on each.
- You don't need `save()` side effects.

The query shape uses `CASE WHEN id = ? THEN value …` — efficient up to
a point, expensive beyond ~1000 rows per statement. The `batch_size`
keeps statements bounded.

### `bulk_create(items, update_conflicts=True, ...)` — upsert

Postgres `INSERT … ON CONFLICT DO UPDATE` in Django form. The
**most contended** pattern in the codebase.

```python
PendingSearchValueUpdate.objects.bulk_create(
    [
        PendingSearchValueUpdate(field_id=fid, row_id=rid)
        for fid in sorted(field_ids)
        for rid in sorted(set(row_ids or [None]))
    ],
    update_conflicts=True,
    unique_fields=["field_id", "row_id"],
    update_fields=["updated_on"],
    batch_size=1000,
)
```

Use when:

- You want "create-or-update": insert if it doesn't exist, update if
  it does.
- A unique constraint defines what counts as "the same row".

Two things to internalise:

1. **`unique_fields` must match a real unique constraint.** Django
   infers nothing here. If the constraint isn't on the table, the
   statement errors at runtime. The combination
   `(field_id, row_id)` above corresponds to a
   `unique_together` declared on `PendingSearchValueUpdate.Meta`.
2. **Sort the input.** Concurrent upserts on overlapping rows in
   different orders deadlock — covered in
   [PostgreSQL locks](../technical/postgresql-locks.md#bulk-create-upsert)
   and the source comment "Ensure order to avoid deadlocks updating
   the same cells". This is **the** non-obvious requirement.

`update_fields` is the columns to update on conflict. Don't include
the unique-constraint columns themselves there — they're the key,
not data.

## `batch_size` — what to pick

Bigger batches: fewer round-trips, less per-statement overhead.
Smaller batches: shorter individual statements, more parallelism
opportunity, less memory pressure.

The numbers used in the codebase (from real usage):

| Operation | `batch_size` |
|---|---|
| Plain `bulk_create` on workspace metadata | 500 |
| `bulk_update` of fields with a few columns | 200 |
| Upsert into `PendingSearchValueUpdate` | 1000 |
| Bulk row-data writes during import | 1000 |
| Audit log writes | 500 |

500–1000 is the right range for most things. Below 100 the per-statement
overhead dominates; above ~5000 single statements get unwieldy and
hold their locks too long.

For very large operations (millions of rows), consider:

- **Splitting into a `RunPython` migration** with chunked iteration —
  see [Migrations](migrations.md#batch-data-migrations).
- **Background job with progress** — see [JobTypes](jobtypes.md).

## What `bulk_*` does NOT do

Both `bulk_create` and `bulk_update` skip:

- Per-row `save()` overrides.
- `pre_save` / `post_save` signals.
- `auto_now` / `auto_now_add` field updates (handled by the database
  via `db_default` if you've set it; otherwise set the values
  manually before the bulk call).
- `clean()` validation.
- M2M relations (set them in a follow-up step).

This is **the** trade-off. If your code relies on `post_save` to
trigger search reindexing, cache invalidation, or realtime
broadcasts, those won't fire from a bulk write. You have to:

- Emit the signal explicitly after the bulk write, **or**
- Call the underlying side-effect functions directly.

The convention in handlers is to do the bulk write inside
`transaction.atomic()` and then explicitly fire `<thing>s_created`
/ `<thing>s_updated` signals with the list of affected rows. Receivers
treat the bulk batch the same way they treat a single-row event.

## Combining with `transaction.on_commit`

Bulk writes are usually inside an `atomic()` block. Any side effects
scheduled from the bulk write (Celery tasks, ws broadcasts, cache
invalidation) belong in `transaction.on_commit(...)` for the same
reasons as single-row writes. See
[Signals and transaction.on_commit](signals-and-on-commit.md).

```python
with transaction.atomic():
    Field.objects.bulk_update(fields, ["name"], batch_size=200)
    transaction.on_commit(lambda: reindex_task.delay(table.id))
```

## Performance budgets

Rough numbers to use as a sanity check, on a healthy production
database:

| Operation | Expected rate |
|---|---|
| Plain `bulk_create` of model rows | ~10k rows/s |
| Upsert (`update_conflicts=True`) | ~5k rows/s |
| `bulk_update` with `CASE WHEN` per id | ~3k rows/s |

If you're well below these, look at:

- Indexes — too many indexes on the table dramatically slows inserts.
- Triggers / constraints — UNIQUE indexes are checked per row.
- The batch size — too small → per-statement overhead dominates.
- Network round-trip — colocated DB vs cross-region matters.

If you're well above, your test data is probably too narrow or your
batch is hitting a cached set. Validate with production-shaped data.

## Anti-patterns

- **`for x in things: x.save()`.** The default reflex; almost always
  wrong for >50 items.
- **`bulk_create` then expecting `post_save` signals to fire.** They
  don't. Emit explicitly.
- **`update_conflicts=True` without sorted input.** Deadlocks under
  contention.
- **`unique_fields` that don't correspond to a real DB constraint.**
  Runtime error.
- **Single `bulk_update` call on hundreds of thousands of rows.**
  The `CASE WHEN` statement becomes huge. Chunk it.
- **Schedule one Celery task per row after a bulk write.** Batch the
  task too — one task with a list of ids beats N tasks with one id
  each.
- **`bulk_create` of M2M through-rows mixed with M2M FK
  cascades.** Sometimes works; sometimes deadlocks. Prefer
  Django's `.add()` for small M2M edits and an explicit
  through-model `bulk_create` for large ones — never mix in one
  transaction.

## Tests

`data_fixture` builds rows individually by default — fine for
correctness tests, slow for performance tests. For tests that
exercise bulk paths, build instances manually and call the same
`bulk_*` method the production code uses. Don't add a "performance"
test that creates 100k rows on every CI run; the CI database isn't
shaped like production and the result is noise.

For query-count assertions, see
[Queries](queries.md). The `assertNumQueries` context manager is
how you prove a bulk-write loop is actually one query, not N.

## Quick reference

| You want to … | Use |
|---|---|
| Insert N new rows | `bulk_create(items, batch_size=500)` |
| Update one column on N existing instances | `bulk_update(items, ["col"], batch_size=200)` |
| Create-or-update by a unique key | `bulk_create(items, update_conflicts=True, unique_fields=[…], update_fields=[…], batch_size=1000)` |
| Delete N rows by id | `Model.objects.filter(id__in=ids).delete()` |
| Update N rows with the same expression | `Model.objects.filter(id__in=ids).update(field=F("field") + 1)` |
| Avoid lock contention | Sort input by the unique key first |
| Fire side effects | Send a `*_created` signal explicitly; receivers don't see bulk writes as `post_save` |
| Schedule a follow-up Celery task | `transaction.on_commit(lambda: task.delay(...))` |

## Related

- [PostgreSQL locks — bulk_create upserts](../technical/postgresql-locks.md#bulk-create-upsert)
  — the deadlock-avoiding sort rule lives there too.
- [Signals and transaction.on_commit](signals-and-on-commit.md) —
  side effects from bulk writes.
- [Queries](queries.md) — the read side: `select_related`,
  `prefetch_related`, `specific_iterator`, query-count tests.
- [Migrations](migrations.md) — `bulk_create` / `bulk_update`
  inside `RunPython` for backfills.
- [Jobs](../technical/jobs.md) — when the bulk write is too big to
  do in a request.
