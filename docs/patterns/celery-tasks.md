# Celery tasks

Recipes for adding async work to Baserow. The companion deep-dive is
[Celery](../technical/celery.md) — read that once to understand workers,
queues, and the time-limit hierarchy. This page is the cookbook.

> **Need progress + cancel + a UI?** You don't want a plain task. You want
> a [Job](../technical/jobs.md). See the
> [JobType walkthrough](jobtypes.md).

## Add a new task

Default to `@app.task` (not `@shared_task`) so the task is bound to
Baserow's Celery app and inherits `BaserowTelemetryTask` (auto-tracing).

```python
from loguru import logger

from baserow.config.celery import app

@app.task(queue="export", soft_time_limit=600, time_limit=660)
def count_widgets(widget_owner_id: int):
    owner = User.objects.get(id=widget_owner_id)
    count = Widget.objects.filter(owner=owner).count()
    logger.info("widget_count owner={} count={}", owner.id, count)
```

Checklist for every new task:

- [ ] **Queue is explicit.** Long-running or low-priority work goes on
  `queue="export"`. Quick (< 1 second) work can use the default queue.
  See [Worker topology](../technical/celery.md#worker-topology).
- [ ] **Time limits are explicit.** Set `soft_time_limit` and `time_limit`
  on the decorator. Don't rely on the 5-minute global default.
- [ ] **Arguments are IDs, not instances.** See below.
- [ ] **Enqueue inside `transaction.on_commit`.** See [Enqueue from a transaction](#enqueue-from-a-transaction).
- [ ] **Tests use `task.run(...)`** (synchronous) or `CELERY_TASK_ALWAYS_EAGER=True`.

## Task arguments: pass IDs, not instances

The Celery serializer is JSON. That has two practical consequences:

1. **Never pass Django model instances.** Pass the primary key. Re-fetch
   in the task body.

   ```python
   # WRONG
   transaction.on_commit(lambda: count_widgets.delay(owner))

   # RIGHT
   transaction.on_commit(lambda: count_widgets.delay(owner.id))
   ```

   Even if a model could be JSON-encoded, the instance the worker received
   would be a stale snapshot — the row may have changed by the time the
   task picks it up. Re-fetching gives you the current state.

2. **Pass primitives only.** `int`, `str`, `bool`, `list`, `dict`. No
   `datetime`, no `Decimal`, no `UUID` (unless stringified). If the payload
   needs to be richer, serialize and deserialize explicitly on both sides.

No model-reference helper exists in the codebase — every task re-queries
for what it needs. The cost is one extra query; the benefit is correctness.

## Enqueue from a transaction

```python
def create_widget(user, name):
    widget = Widget.objects.create(user=user, name=name)
    transaction.on_commit(lambda: process_widget.delay(widget.id))
    return widget
```

Without `transaction.on_commit`, the task can start before the transaction
commits — at which point it can't find the row it was given. The bug is
intermittent (race between commit and worker pickup) and painful to chase.

The [Job framework](../technical/jobs.md) already wraps the enqueue in
`transaction.on_commit` and adds a safety net for Redis-down scenarios
(via `JobHandler.create_and_start_job`). For Jobs you don't need to write
this yourself; for plain tasks you do.

## Time limits

Pick them deliberately:

- **`soft_time_limit`** — what's a reasonable upper bound for a healthy
  execution? Set it to ~1.5–2× that. When exceeded, `SoftTimeLimitExceeded`
  is raised inside the task — you can catch it and write a "timed out"
  state somewhere.
- **`time_limit`** (hard) — soft limit + a small grace period (30–60 s).
  When exceeded, the worker process is killed; nothing in the task body
  runs after that point.

```python
@app.task(
    queue="export",
    soft_time_limit=300,   # 5 minutes
    time_limit=360,        # 6 minutes
    autoretry_for=(SoftTimeLimitExceeded,),  # optional: retry if soft-limit hit
)
def long_running_thing(arg_id: int):
    ...
```

Globals (see [Celery > Time limits](../technical/celery.md#time-limits) for
defaults). If your task can plausibly run longer than the 5-minute global,
**override locally**. Inheriting silently is how production tasks end up
killed for no obvious reason.

## Periodic tasks

Hook `app.on_after_finalize` in the module that owns the task. Don't reach
for a central schedule dict.

```python
from datetime import timedelta
from baserow.config.celery import app

@app.task(queue="export")
def cleanup_expired_widgets():
    Widget.objects.filter(expired_at__lt=timezone.now()).delete()

@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(minutes=settings.WIDGET_CLEANUP_INTERVAL_MINUTES),
        cleanup_expired_widgets.s(),
    )
```

Schedules can be:

- `timedelta(minutes=N)` — fixed interval.
- `crontab(hour=3, minute=0)` — cron-style; useful for nightly tasks.
- A `solar(...)` event — rare.

The `redbeat` scheduler stores schedules in Redis, so they survive
restarts and coordinate across replicas. You can run multiple beat
processes safely.

Pair periodic tasks with [`Singleton`](#singleton-tasks) when overlap
between ticks would cause problems.

## Singleton tasks

Use `celery-singleton` when concurrent execution of the same task would
be incorrect (mostly: cleanups, indexing, anything writing shared state).

```python
from celery_singleton import Singleton
from baserow.config.celery import app

CLEANUP_TIME_LIMIT = 600  # 10 minutes

@app.task(
    base=Singleton,
    queue="export",
    raise_on_duplicate=False,        # silent no-op on duplicate enqueue
    lock_expiry=CLEANUP_TIME_LIMIT,  # MUST set, match the time_limit
    soft_time_limit=CLEANUP_TIME_LIMIT,
    time_limit=CLEANUP_TIME_LIMIT,
)
def cleanup_widget_caches():
    ...
```

Three parameters worth knowing:

| Parameter | What it does |
|---|---|
| `base=Singleton` | Replaces the default `Task` base with the singleton-aware one. |
| `raise_on_duplicate=False` | Preferred default. A duplicate enqueue silently no-ops. Set `True` only when the caller needs to know. |
| `unique_on=...` | Keys the lock on a subset of arguments. Example: `unique_on="table_id"` lets different tables run concurrently while the same table cannot. |
| `lock_expiry=...` | **Mandatory in practice.** Without it, a worker crash leaves a permanent lock. Always match the `time_limit`. |

> **Singleton ≠ idempotent.** Singleton prevents *overlap*, not *duplicate
> work*. If the same arguments can re-enqueue after a completed run, the
> body still needs to be idempotent — or use the
> `SingletonAutoRescheduleFlag` pattern (see
> `baserow.contrib.database.search.tasks` for a real example) to handle
> "an update arrived while I was running".

## Retry strategies

Three patterns, in order of preference:

### 1. Auto-retry on a specific exception (declarative)

```python
from celery.exceptions import SoftTimeLimitExceeded

@app.task(
    bind=True,
    queue="export",
    autoretry_for=(SoftTimeLimitExceeded,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
)
def email_summary(self, now=None):
    ...
```

Use when:
- The exception type alone decides whether to retry.
- The retry delay can be a fixed countdown or auto-backoff.

### 2. Manual `self.retry()`

```python
@app.task(bind=True, queue="export")
def email_summary(self, now=None):
    if redis_lock_busy():
        raise self.retry(args=[now], countdown=60)
    ...
```

Use when:
- Retry decision depends on runtime state (a value, a flag, an external
  service).
- You need to change the args on retry.

### 3. Hand-rolled exponential backoff with attempt counter

```python
@app.task(
    bind=True,
    queue="export",
    max_retries=settings.BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL,
)
def call_webhook(self, webhook_id, ..., retries=0, **kwargs):
    success = try_deliver(webhook_id)
    if not success and retries < settings.BASEROW_WEBHOOKS_MAX_RETRIES_PER_CALL:
        kwargs["retries"] = retries + 1
        self.retry(countdown=2**retries, kwargs=kwargs)
```

Use when:
- You need the attempt number visible in the task body (logging,
  surfacing in the UI).
- Exponential backoff matters and a `retry_backoff=True` on the decorator
  isn't enough.

### Don't retry Jobs

The [Job framework](../technical/jobs.md) treats `failed` as terminal. If
your work makes sense to retry, you probably want a plain task — not a
Job. Jobs assume the user is watching and would notice a "retry happening
in the background"; tasks don't carry that contract.

## Testing tasks

Two options:

```python
# 1. Run the function directly (no broker, no worker).
def test_count_widgets():
    setup_widgets()
    count_widgets(owner.id)
    assert ...
```

```python
# 2. Eager mode: .delay() runs synchronously.
@pytest.fixture(autouse=True)
def _celery_eager(settings):
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True

def test_create_widget_enqueues_processing():
    user, widget = create_widget(name="x")
    # process_widget already ran (eager) — assert on its side effects
```

Direct call is faster and simpler. Use eager mode when you care about the
`.delay()` path being exercised (e.g. asserting that
`transaction.on_commit` actually triggered the enqueue).

## Common pitfalls

| Symptom | Likely cause |
|---|---|
| Task runs but can't find the row. | Enqueued outside `transaction.on_commit`. |
| Task killed at exactly 5 minutes, no warning. | Inheriting global `CELERY_TASK_SOFT_TIME_LIMIT=300`. Set the limits on the decorator. |
| Task runs twice for the same input. | Singleton not configured, or `unique_on` doesn't include the discriminator. |
| Singleton lock stuck after a crash. | `lock_expiry` not set. Always set it; match the `time_limit`. |
| Worker holds dead DB connections. | The prerun/postrun handlers in `config/celery.py` should already cover this — but bare `@shared_task` outside Baserow's app won't pick them up. Use `@app.task`. |
| `JSONDecodeError` at enqueue time. | A non-JSON-safe argument (datetime, UUID, model). Pass primitives. |

## See also

- [Celery (deep dive)](../technical/celery.md) — the architectural side
  of this page.
- [Jobs (deep dive)](../technical/jobs.md) — when a task isn't enough.
- [JobType walkthrough](jobtypes.md) — end-to-end how-to for the framework
  on top of Celery.
- [Observability](observability.md) — logs and tracing for task code.
