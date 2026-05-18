# Database migrations (zero-downtime)

Baserow migrations run while the previous release may still be serving traffic.
During that window, old code reads and writes the new schema. A migration that
old code cannot tolerate is a deploy outage.

For Postgres lock details see [PostgreSQL locks](../technical/postgresql-locks.md).

## Compatibility Window

```
v1 running
  -> migration runs
v1 running on schema v2
  -> deploy v2
v2 running on schema v2
```

The safe rule: expand first, move code second, contract later.

## Core Patterns

### Nullable -> backfill -> NOT NULL

For a new required column:

1. Add it nullable with no DB default.
2. Backfill in batches.
3. In a later release, mark it `NOT NULL`.

```python
operations = [
    migrations.AddField(
        model_name="widget",
        name="size_kb",
        field=models.IntegerField(null=True, default=None),
    ),
    migrations.RunPython(populate_size_kb, migrations.RunPython.noop),
]
```

### Batch data migrations

Use historical models from `apps.get_model()`, stream reads, and bulk-write in
bounded chunks:

```python
from baserow.core.utils import grouper

def populate(apps, schema_editor):
    Widget = apps.get_model("database", "Widget")
    rows = Widget.objects.all().iterator(chunk_size=1000)
    for chunk in grouper(1000, rows):
        Widget.objects.bulk_update(
            [update_one(row) for row in chunk],
            ["size_kb"],
            batch_size=100,
        )
```

Never import the current model class inside a migration function.

### Use concurrent indexes

Indexes on populated tables should use `CONCURRENTLY`, which requires
`atomic = False` on the migration class:

```python
class Migration(migrations.Migration):
    atomic = False

    operations = [
        migrations.RunSQL(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS widget_size_idx "
            "ON widget (size_kb);",
            reverse_sql="DROP INDEX CONCURRENTLY IF EXISTS widget_size_idx;",
        ),
    ]
```

`RunPython(..., atomic=False)` is not the same thing; set `atomic = False` on
the migration class when the whole migration must escape the wrapping
transaction.

### Make operations reversible

Every `RunPython` and `RunSQL` should have `reverse_code` or `reverse_sql`,
even if it is `migrations.RunPython.noop`. Irreversible migrations are hard to
recover from during incidents.

## Operation Recipes

| Change | Safe shape |
|---|---|
| Add nullable column | One `AddField(..., null=True, default=None)`. |
| Add required column | Nullable -> batched backfill -> later `AlterField(null=False)`. |
| Rename column | Add new column, dual-write/read, drop old column in later release. Single-step `RenameField` breaks old code. |
| Drop column | Stop using it in one release; drop it in a later release. |
| Drop table | Remove all usage and dependent FKs first; delete model later. |
| Add index on populated table | `atomic = False` + `CREATE INDEX CONCURRENTLY`. |
| Add unique constraint | Deduplicate first, create unique index concurrently, attach constraint with `USING INDEX`. |
| Add check or FK on large table | Add `NOT VALID`, then `VALIDATE CONSTRAINT` later. Ensure child FK columns are indexed. |
| Change column type on large table | Add new column, backfill, switch reads/writes, drop old column later. |

Changes on new or empty tables are usually safe in one migration.

## `RunPython` Rules

- Use `apps.get_model(...)`, never current imports.
- Avoid no-op writes: filter with `WHERE field IS DISTINCT FROM ...` or
  `WHERE field IS NOT NULL`.
- Use a cheap `SELECT EXISTS` pre-check when an expensive `UPDATE` may be
  empty and no new matching rows can appear during the migration.
- Keep transactions small when touching many tables or rows.
- Assume self-hosters may have low `max_locks_per_transaction`; do not hold a
  long transaction while iterating across many user tables.
- Do not enqueue Celery tasks from migrations.

## User Tables

User data tables (`database_table_<id>`) are changed at runtime by field
operations, not Django migrations. If you touch the runtime schema editor, use
[`safe_django_schema_editor`](../technical/postgresql-locks.md#schema-editor-safe_django_schema_editor)
and avoid holding DDL locks across long jobs.

## Bigger Changes

If the migration is a large rewrite or backfill:

1. Prefer several small, reversible migrations.
2. Move the data work to a management command when it cannot fit safely in the
   deploy.
3. Use a Job only when the product can tolerate a visible "not fully
   backfilled yet" state.

## Testing

- Let the normal backend test DB setup apply every migration.
- Unit-test risky `RunPython` functions with pre/post states.
- Test reversibility for high-risk migrations.
- Benchmark heavy migrations on production-shaped data when possible.

## Pre-Merge Checklist

- [ ] Old code can run against the new schema.
- [ ] Required columns are staged through nullable + backfill.
- [ ] Indexes on populated tables use `CONCURRENTLY`.
- [ ] Data migrations are batched and use `apps.get_model`.
- [ ] `RunPython` / `RunSQL` has a reverse operation.
- [ ] Drops and renames are staged across releases.
- [ ] No Celery work is scheduled from the migration.
- [ ] User-table DDL uses the safe schema-editor pattern.

## Related

- [Creating a feature](creating-features.md).
- [PostgreSQL locks](../technical/postgresql-locks.md).
- [Queries](queries.md).
- [Signals and `transaction.on_commit`](signals-and-on-commit.md).
