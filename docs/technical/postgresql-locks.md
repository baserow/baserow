# PostgreSQL locking and Baserow

This guide is the working knowledge a backend engineer needs about Postgres
locks in Baserow: the lock types that actually show up in our code, the
patterns we use to acquire and release them, and the gotchas that have
caught us in the past. It is not a Postgres reference — for that, the
[Postgres locking docs][pg-docs] are authoritative and
[pglocks.org][pglocks] is an excellent companion that visualises which lock
modes conflict.

[pg-docs]: https://www.postgresql.org/docs/current/explicit-locking.html
[pglocks]: https://pglocks.org/

## What you actually need to know about Postgres locks

There are three layers of locks that come up in day-to-day Baserow work:

1. **Row-level locks**, acquired by `UPDATE`, `DELETE`, or `SELECT … FOR
   UPDATE`. Two transactions touching different rows of the same table don't
   block each other; two touching the same row do.
2. **Table-level locks**, acquired implicitly by every statement (most
   statements take a non-conflicting mode like `ACCESS SHARE` or `ROW
   EXCLUSIVE`) and explicitly by `LOCK TABLE … IN <mode>`. DDL takes
   `ACCESS EXCLUSIVE`, which conflicts with everything.
3. **Advisory locks** (`pg_advisory_lock`, `pg_advisory_xact_lock`). Named
   by an integer; mean nothing to Postgres beyond mutual exclusion. We use
   them as cross-process mutexes.

Locks are released at transaction end — `COMMIT` or `ROLLBACK`. That single
fact is the source of nearly every locking bug: a transaction holds a row
lock during a slow network call, every other writer queues behind it. Keep
transactions short, do I/O outside them, and acquire locks in a consistent
order.

## The patterns we use, with examples

### 1. `select_for_update()` — lock then update

The canonical handler pattern. Read with a row lock, mutate, save, commit.

```python
# backend/src/baserow/core/handler.py:526
def get_workspace_for_update(self, workspace_id: int) -> WorkspaceForUpdate:
    return self.get_workspace(
        workspace_id,
        base_queryset=Workspace.objects.select_for_update(of=("self",)),
    )
```

`of=("self",)` is the variant we reach for by default. Without it, Django
will lock every joined table too, which is rarely what you want and is a
common source of unexpected contention. The companion convention is the
`*ForUpdate` type alias on the model so the type system tracks "this is a
locked instance" — see `WorkspaceForUpdate` and friends in the same module.

Examples worth reading:

- `backend/src/baserow/core/snapshots/handler.py:247` — locks a snapshot
  before transitioning its state.
- `backend/src/baserow/core/action/handler.py:105` — locks the action group
  during undo/redo so two concurrent users on the same workspace can't
  corrupt the undo stack.
- `backend/src/baserow/contrib/database/rows/handler.py:645` — locks the
  row before applying an update; pairs with the row signal pipeline.

### 2. Implicit row locks via `.update()` (no `select_for_update`)

`UPDATE` implicitly takes `ROW EXCLUSIVE` on the table and a row-level lock
on every row it touches. When the write is **idempotent or commutative**
and you don't need to read-then-decide, skip `select_for_update` entirely:

```python
# backend/src/baserow/contrib/database/views/handler.py:271
View.objects.filter(id__in=[v.id for v in views]).update(db_index_name=None)
```

Or with `F()` for counter-style increments:

```python
SomeModel.objects.filter(pk=pk).update(counter=F("counter") + 1)
```

Use this when:

- The new value is a pure function of the old value (`F()` expressions).
- You're clearing/setting a flag and don't care about the previous value.
- You're bulk-updating many rows and a `SELECT FOR UPDATE` would force a
  per-row roundtrip.

Don't use it when you need to decide *whether* to write based on the
current value — that's a read-modify-write race and needs `select_for_update`.

### 3. `nowait=True` + retry — fail-fast on contention

When you don't want to queue behind a contended row, ask for the lock with
`nowait=True`. Postgres immediately raises `OperationalError("could not
obtain lock")` if it can't grant it. Catch that and either retry, fail, or
reschedule.

```python
# backend/src/baserow/contrib/database/webhooks/tasks.py:97
with transaction.atomic():
    try:
        webhook = TableWebhook.objects.select_for_update(
            of=("self",), nowait=True,
        ).get(id=webhook_id, active=True)
    except OperationalError as e:
        if "could not obtain lock" in e.args[0]:
            # Another worker is already firing this webhook. Re-enqueue
            # so we don't run two deliveries concurrently.
            enqueue_webhook_task(webhook_id, event_id, args, kwargs)
            return
        raise
```

The webhook code uses this as a singleton-per-webhook guard: only one
delivery may be in flight for a given webhook at a time, and contenders
re-enqueue themselves with Celery's natural backoff instead of holding
DB connections.

Field schema operations use the same primitive but driven by a setting:

```python
# backend/src/baserow/contrib/database/fields/handler.py:261
Field.objects.select_related("table").select_for_update(
    of=("self", "table"), nowait=settings.BASEROW_NOWAIT_FOR_LOCKS,
)
```

`BASEROW_NOWAIT_FOR_LOCKS` lets ops turn fail-fast on globally — useful
when a slow field operation is at risk of blocking unrelated writes for
seconds.

For pure deadlock retries (different from `nowait` contention),
`baserow.core.db.atomic_with_retry_on_deadlock`
(`backend/src/baserow/core/db.py:858`) is a decorator that re-runs the
function on `DeadlockDetected` with exponential backoff. The wrapped
function **must be idempotent** — read the docstring before reaching for
it.

### 4. `skip_locked=True` — claim what's free, ignore what's not

The work-queue pattern. Each worker grabs whatever rows it can lock and
leaves contested ones for someone else.

```python
# backend/src/baserow/core/notifications/tasks.py:23
with transaction.atomic():
    queued = (
        NotificationRecipient.objects.filter(queued=True)
        .select_related("notification", "notification__sender")
        .order_by("recipient_id", "-created_on")
        .select_for_update(of=("notification",), skip_locked=True)
    )
    for nr in queued:
        ...
```

Two workers running `send_queued_notifications_to_users` at the same time
won't fight each other, won't double-send, and won't stall — they just
split the queue. The `of=("notification",)` is the key detail: we lock the
notification row, not the recipient row, so two recipients of the same
notification still serialise (so they always see consistent broadcast
data) while different notifications go in parallel.

Use this whenever the workload is "pop the next available unit of work".
Avoid it when correctness requires that *every* row be processed in this
run — `skip_locked` silently omits locked rows from the result set.

### 5. `bulk_create(..., update_conflicts=True)` — atomic upsert { #bulk-create-upsert }

Postgres `INSERT … ON CONFLICT DO UPDATE` in Django form. No explicit lock
acquisition on our side; Postgres handles the row-level locking implicitly
and consistently. The most contended example in the codebase is the search
queue:

```python
# backend/src/baserow/contrib/database/search/handler.py:638
# Ensure order to avoid deadlocks updating the same cells.
ordered_field_ids = sorted(field_ids)
ordered_row_ids = sorted(set(row_ids or [None]))
PendingSearchValueUpdate.objects.bulk_create(
    [
        PendingSearchValueUpdate(field_id=field_id, row_id=row_id)
        for field_id in ordered_field_ids
        for row_id in ordered_row_ids
    ],
    update_conflicts=True,
    unique_fields=["field_id", "row_id"],
    update_fields=["updated_on"],
    batch_size=1000,
)
```

Two details to internalise:

- **Deterministic ordering is mandatory under contention.** Two concurrent
  upserts touching `(A, B)` from one caller and `(B, A)` from another will
  deadlock. Sorting the input list eliminates the cycle. The comment in the
  search handler is there for a reason.
- **`unique_fields` must match a real unique constraint** in the database.
  Django infers nothing; if the constraint isn't there, you'll get a runtime
  error.

Another example: `_bulk_create_or_update` in
`backend/src/baserow/contrib/database/table/handler.py:160` for table usage
counters (`row_count`, `storage_usage`).

### 6. Advisory locks — cross-process singletons

For "only one process in the cluster does this at a time", an advisory
lock is cheaper and clearer than reserving a row.

```python
# backend/src/baserow/core/management/commands/locked_migrate.py:64
cursor.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])
```

This is the wrapper around `manage.py migrate` that prevents two
containers from running migrations simultaneously during a rolling deploy.
Three things to note:

- `pg_advisory_xact_lock` (not `pg_advisory_lock`) so it auto-releases on
  transaction end — pgbouncer in transaction mode would otherwise leak
  session-scoped locks across pooled connections.
- A separate connection holds the lock; the actual migrate runs on the
  normal connection, because some Django migrations are non-atomic and
  can't run inside our holding transaction.
- The lock ID comes from `settings.MIGRATION_LOCK_ID` — pick a stable
  integer per logical lock and document it.

### 7. Explicit `LOCK TABLE`

Reach for this only when row-level locking can't express what you need —
typically "prevent any writes to this table for the duration of a
schema-level operation".

```python
# backend/src/baserow/contrib/database/views/handler.py:607
if nowait:
    first_sql_to_run = (
        sql.SQL("LOCK TABLE {0} IN SHARE MODE NOWAIT"),
        [sql.Identifier(view.table.get_database_table_name())],
    )
```

This is the view index rebuild: take `SHARE` (which blocks writers but not
readers), with `NOWAIT` so we fail fast if the table is busy and let the
caller reschedule. The `LockedAtomicTransaction` context manager in
`backend/src/baserow/core/db.py:81` is a similar idea — a context manager
that issues a bare `LOCK TABLE <name>` (defaulting to `ACCESS EXCLUSIVE`)
at the start of an atomic block. The class docstring is appropriately
cautious: "should be used with caution, since it has impacts on
performance, for obvious reasons."

## Isolation levels and snapshot reads

Locks and isolation levels solve different problems and the choice between
them is independent. Locks govern who can touch a specific row or table
*right now*; the isolation level governs what *committed-by-others* changes
your transaction is allowed to observe over its lifetime. For most of the
patterns above the default (`READ COMMITTED`) is correct — but
**long-running reads that must see a consistent snapshot** (exports,
duplicates, data syncs, structure imports) need to combine an isolation
level *and* metadata locks.

### The three levels in `baserow.core.db.IsolationLevel`

`backend/src/baserow/core/db.py:316`:

| Level | What your transaction sees | When we use it |
|---|---|---|
| `READ COMMITTED` (Postgres default) | Each statement sees a fresh snapshot of all *committed* data. Two reads in the same transaction can return different values. | Everything not explicitly listed below. |
| `REPEATABLE READ` | Every statement in the transaction sees the same snapshot, taken at the first non-empty statement. Phantom-free for the data you read. | Exports, table duplicates, data syncs, schema-aware imports. |
| `SERIALIZABLE` | As-if-serial execution: the engine aborts your transaction if the outcome could differ from some serial order. | Not currently used in core code. Available via `IsolationLevel.SERIALIZABLE` if you need it. |

The mechanism is a single statement at the start of the atomic block:

```python
# backend/src/baserow/core/db.py:322
@contextlib.contextmanager
def transaction_atomic(
    using=None, savepoint=True, durable=False,
    isolation_level: Optional[str] = None,
    first_sql_to_run_in_transaction_with_args=None,
):
    with transaction.atomic(...) as a:
        if isolation_level:
            cursor.execute("SET TRANSACTION ISOLATION LEVEL %s" % isolation_level)
        if first_sql_to_run_in_transaction_with_args:
            cursor.execute(first_sql.format(*first_args))
        yield a
```

The `first_sql_to_run_in_transaction_with_args` parameter is not a generic
convenience — it exists specifically to take the metadata lock as the
**first** statement, which is the moment Postgres opens the
`REPEATABLE READ` snapshot. See below.

### The MVCC caveat: REPEATABLE READ is not enough on its own

Postgres' MVCC snapshot covers row visibility. It does **not** protect
against DDL — `ALTER TABLE`, `DROP COLUMN`, `DROP TABLE` are not
MVCC-safe and can invalidate a snapshot mid-read. See [MVCC
caveats][mvcc-caveats] in the Postgres docs.

[mvcc-caveats]: https://www.postgresql.org/docs/current/mvcc-caveats.html

This matters specifically in Baserow because user "fields" and "tables"
are first-class concepts that issue real DDL: adding a field is `ALTER
TABLE … ADD COLUMN`, deleting one is `ALTER TABLE … DROP COLUMN`. If you
export a database under plain `REPEATABLE READ` while another request
deletes a field, your export blows up halfway through with a snapshot
inconsistency.

The fix is to **lock the field and table metadata rows** at the start of
the same transaction with `FOR KEY SHARE`. Other readers and writers of
the user data are unaffected (key-share is a weak lock), but anything
trying to *alter the schema* of those tables blocks until the export
finishes.

### The three snapshot-read helpers

All three live in `backend/src/baserow/contrib/database/db/atomic.py`.

**`read_repeatable_single_database_atomic_transaction(database_id)`** —
`atomic.py:7`. `REPEATABLE READ` + `FOR KEY SHARE` on every field and
table in the database. Used by `DatabaseApplicationType` for exports and
duplicates (`backend/src/baserow/contrib/database/application_types.py:104`).
This is the right choice when you need a snapshot across multiple tables
in the same database (cross-table link rows, lookups, formulas).

**`read_repeatable_read_single_table_transaction(table_id)`** —
`atomic.py:99`. Same idea, scoped to one table. Used by:

- Table duplicate (`backend/src/baserow/contrib/database/table/job_types.py:45`).
- Data sync (`backend/src/baserow/contrib/database/data_sync/job_types.py:102`).
- Field-level snapshot jobs (`backend/src/baserow/contrib/database/fields/job_types.py:50`).

**`read_committed_single_table_transaction(table_id)`** — `atomic.py:55`.
`FOR KEY SHARE` lock on the table's metadata, but **stays in
`READ COMMITTED`**. Use this when you want protection from concurrent DDL
but don't need a consistent snapshot of the row data — typically because
you're streaming new data in (file import) rather than reading the
existing table whole. Used by the file import job
(`backend/src/baserow/contrib/database/file_import/job_types.py:191`).

### Why per-application transactions instead of one big one

The export job docstring is explicit about it:

```python
# backend/src/baserow/core/job_types.py:224
@contextmanager
def _empty_transaction_context():
    """
    Each application is isolated, so a single transaction for all of them
    together is unnecessary and increases the risk of incurring into the
    `max_locks_per_transaction` error. The `import_export_handler` creates a
    transaction for each application in a `repeatable_read` isolation level
    to guarantee consistency in the data read.
    """
    yield
```

This is the intersection of the two big concerns in this doc: snapshot
consistency wants long transactions, but lock budget wants short ones.
Resolution: one `REPEATABLE READ` transaction *per application*, not one
across the whole job. Each application's snapshot is internally
consistent; the job as a whole is not, which is the right trade-off
because applications don't reference each other.

### Decision rule

- Need to **see one snapshot** across multiple statements? `REPEATABLE READ`.
- Need that snapshot to **survive concurrent field/schema changes**?
  Combine with `FOR KEY SHARE` on the metadata — use the helpers, don't
  reinvent.
- Need true serialisability for some new concurrent algorithm?
  `SERIALIZABLE`, and be ready to handle `SerializationFailure` with a
  retry loop similar to `atomic_with_retry_on_deadlock`.
- Anything else: stay on the default (`READ COMMITTED`).

## Baserow-specific gotchas

### `max_locks_per_transaction` and user tables

Each generated user data table is a real Postgres table. Operations that
touch every table in a database — duplication, snapshot export, snapshot
restore — open one transaction and acquire locks on thousands of tables.
Postgres caps the per-transaction lock count via
`max_locks_per_transaction` (default 64; multiplied by `max_connections`
for the cluster-wide pool).

If you exceed it, you get `OperationalError: out of shared memory … You
might need to increase max_locks_per_transaction`. We detect that exact
message:

```python
# backend/src/baserow/core/handler.py:2182
@staticmethod
def is_max_lock_exceeded_exception(exception: OperationalError) -> bool:
    return (
        "You might need to increase max_locks_per_transaction"
        in exception.args[0]
    )
```

Used at `backend/src/baserow/core/handler.py:1557` during duplication to
raise a typed `DuplicateApplicationMaxLocksExceededException`, and at
`backend/src/baserow/core/snapshots/handler.py:408` for snapshots. The job
docstring at `backend/src/baserow/core/job_types.py:227` documents why
batching matters here.

**Operationally**: if you're hosting Baserow and a customer's snapshot
fails with this, raise `max_locks_per_transaction` in `postgresql.conf`
(needs a restart) — find the config file via `SHOW config_file;` in psql.
On managed databases, ask your provider. As a rule of thumb, set it to
something like `max(64, expected_tables_per_workspace * 4)` to leave
headroom for join targets and indexes.

### Schema editor: `safe_django_schema_editor`

DDL on user data tables goes through
`backend/src/baserow/contrib/database/db/schema.py:395`. Always use this
context manager rather than Django's raw `connection.schema_editor()`. It
fixes two upstream bugs (broken `__exit__` on deferred SQL errors;
double-create of the through table on self-referencing link rows) and
lets you opt out of the surrounding atomic block via `atomic=False` —
critical for long-running operations like duplicate/snapshot where holding
DDL locks for the entire run would block writes across the whole database.

### Deadlocks: order is destiny

Any time you lock more than one row in one transaction — `bulk_create`
upserts, multi-row `select_for_update`, foreign key cascades — sort the
input on a stable key before issuing the statement. Postgres detects
deadlocks and aborts one transaction with `DeadlockDetected`, but each
hit is a wasted transaction and an error log. Sort first.

If you can't sort (e.g. the rows come from user input across a join),
wrap the function in `atomic_with_retry_on_deadlock` so the rare detected
deadlock is automatically retried.

## Quick decision guide

| Situation | Use |
|---|---|
| Read a row, mutate it, save it | `select_for_update(of=("self",))` |
| Bump a counter / set a flag, no read-decide | plain `.update(...)` (often with `F()`) |
| Singleton task — don't run two copies | `select_for_update(of=..., nowait=True)` + re-enqueue on `OperationalError` |
| Queue-style worker, claim what's free | `select_for_update(of=..., skip_locked=True)` |
| Insert-or-update many rows | `bulk_create(..., update_conflicts=True)` with sorted input |
| One process in the cluster at a time | `pg_advisory_xact_lock(id)` in a holding connection |
| Block writers during a schema-level op | `LOCK TABLE … IN SHARE MODE NOWAIT` + atomic block |
| Multi-table DDL on user tables | `safe_django_schema_editor(atomic=...)` |
| Generic deadlock-resilience for an idempotent fn | `@atomic_with_retry_on_deadlock` |
| Consistent snapshot read of one table (export, duplicate) | `read_repeatable_read_single_table_transaction(table_id)` |
| Consistent snapshot read across a database | `read_repeatable_single_database_atomic_transaction(database_id)` |
| Protect a long read from concurrent DDL, snapshot not needed | `read_committed_single_table_transaction(table_id)` |

## Diagnosing lock issues in production

- **Currently held / waiting locks**:
  `SELECT * FROM pg_locks JOIN pg_stat_activity USING (pid);` — match on
  `granted=false` to find the queue.
- **Blocking chains**: see the Postgres wiki's
  [Lock Monitoring][pg-monitor] query.
- **Deadlock log**: `log_lock_waits = on` in `postgresql.conf` turns every
  wait longer than `deadlock_timeout` (default 1s) into a log line. Worth
  enabling in dev and staging.
- **Baserow side**: any `OperationalError` with `"could not obtain lock"`
  or `"deadlock detected"` should be cross-referenced with the patterns
  above before being treated as transient.

[pg-monitor]: https://wiki.postgresql.org/wiki/Lock_Monitoring

## Related

- [pglocks.org][pglocks] — interactive matrix of conflicting lock modes.
- [Postgres explicit locking docs][pg-docs] — authoritative reference.
- [Workspace search](workspace-search.md) and
  [Table rows full-text search](table-rows-search.md) — the search update
  pipeline is the most concentrated worked example of upsert + skip-locked
  + deadlock-avoiding ordering in the codebase.
- [Caching](caching.md) — some caches are invalidated under locks held by
  the writer; the interaction is worth understanding.
