# Celery in Baserow

Celery is the async runtime under everything that shouldn't block a
request. This page explains the Baserow-specific setup — workers, queues,
time-limit hierarchy, periodic-task mechanism, singleton mechanism — and
links out to the conceptually adjacent system, [Jobs](jobs.md).

For the cookbook side ("how do I write a task / periodic / singleton?")
see [Celery tasks](../patterns/celery-tasks.md).

## App definition and broker

The Celery app is instantiated in
`backend/src/baserow/config/celery.py`:

```python
app = Celery("baserow")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
app.Task = BaserowTelemetryTask
```

- **Broker and result backend** — Redis (same URL for both). Configured via
  `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` in
  `backend/src/baserow/config/settings/base.py`.
- **Result expiry** — `CELERY_RESULT_EXPIRES = 3600` (1 hour). Task results
  aren't the primary state mechanism; long-running work uses the
  [Job framework](jobs.md) which has its own cache layer.
- **Scheduler** — `redbeat.RedBeatScheduler` (Redis-backed). The schedule
  survives restarts and uses a Redis lock to coordinate replicas, so you
  can run multiple beat processes safely.
- **Serializer** — JSON. Implication: task arguments must be JSON-safe
  primitives; never pass Django model instances. The [tasks
  cookbook](../patterns/celery-tasks.md#task-arguments-pass-ids-not-instances)
  explains the rule.
- **Custom base task** — `BaserowTelemetryTask` attaches the task name to
  OpenTelemetry baggage on every call. Set via `app.Task = ...`, so
  every `@app.task` and `@shared_task` inherits it.

## Worker topology

Baserow runs **two worker processes** with different queues:

| Worker | Queues | Purpose |
|---|---|---|
| `celery-worker` (default) | `celery`, `automation_workflow` | Quick / latency-sensitive tasks: realtime broadcast, notifications, emails, webhook delivery, automation workflows. |
| `celery-export-worker` | `export` | Long-running tasks: exports, snapshots, trash cleanup, search reindex, usage calculation, and **all `run_async_job` invocations**. |

Routing is configured via `CELERY_TASK_ROUTES` in the settings module, or
per-task via `@app.task(queue="...")`. Both styles coexist; prefer the
decorator for tasks colocated with their domain, the central dict for
third-party tasks where you can't change the decorator.

`BASEROW_RUN_MINIMAL=true` collapses both workers into a single process
for memory-constrained deployments. Tasks still route by queue name; one
worker just consumes both queues.

## Time limits

Every task has **two** limits:

- **`soft_time_limit`** — raises `SoftTimeLimitExceeded` inside the task,
  giving the task a chance to clean up (write `failed` state, close
  handles).
- **`time_limit`** (hard) — kills the worker process. Should always be
  slightly greater than the soft limit.

Defaults (in `base.py`):

```python
CELERY_TASK_SOFT_TIME_LIMIT = 300   # 5 minutes
CELERY_TASK_TIME_LIMIT = CELERY_TASK_SOFT_TIME_LIMIT + 60
```

Several places override the defaults:

| Task | Soft | Hard | Env var |
|---|---|---|---|
| `run_async_job` (Job framework) | 1800s | default + 60s | `BASEROW_JOB_SOFT_TIME_LIMIT` |
| Export tasks | 3600s | 3661s | hard-coded |
| Search reindex | 3600s | 3600s | `BASEROW_CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT` |

The recipe for choosing time limits when you write a new task lives in the
[tasks cookbook](../patterns/celery-tasks.md#time-limits).

## Periodic tasks — the mechanism

Baserow does **not** use a central `CELERY_BEAT_SCHEDULE` dict. Each app
module that owns periodic work hooks `app.on_after_finalize` and calls
`sender.add_periodic_task(...)`:

```python
@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        timedelta(minutes=settings.BASEROW_JOB_CLEANUP_INTERVAL_MINUTES),
        clean_up_jobs.s(),
    )
```

This pattern keeps the schedule colocated with the task definition and
avoids a single registry every periodic task has to touch. Combined with
the `redbeat` scheduler, schedules survive restarts and coordinate across
replicas.

A few real periodic tasks running in production:

| Task | Schedule | What it does | Where |
|---|---|---|---|
| `clean_up_jobs` | 5 min | Expire old/timed-out jobs. | `backend/src/baserow/core/jobs/tasks.py` |
| `run_calculate_storage` | 30 min | Workspace storage usage. | `backend/src/baserow/core/usage/tasks.py` |
| `clean_up_old_jobs` (exports) | 5 min | Remove old export jobs + files. | `backend/src/baserow/contrib/database/export/tasks.py` |
| `periodic_check_pending_search_data` | 15 min | Pick up search reindex backlog. | `backend/src/baserow/contrib/database/search/tasks.py` |
| `run_periodic_fields_updates` | 10 min | Recompute periodic field types. | `backend/src/baserow/contrib/database/fields/tasks.py` |

To add one, see the [periodic-task recipe](../patterns/celery-tasks.md#periodic-tasks).

## Singleton tasks — the mechanism

Baserow uses **`celery-singleton`** to prevent concurrent execution of a
task. The library acquires a Redis lock at enqueue time keyed on the
task name + arguments; if a second enqueue arrives while the first is
running, it's silently dropped (or rejected, depending on configuration).

Key details:

- **Custom backend.** `baserow.celery_singleton_backend` provides a
  `RedisBackendForSingleton` that reuses Baserow's existing Redis
  connection pool. Configured automatically via the Celery app.
- **`unique_on=...`** keys the lock on a subset of arguments. Example:
  `update_search_data(table_id)` uses `unique_on="table_id"` so different
  tables can index concurrently while the same table cannot.
- **`raise_on_duplicate=False`** is the preferred default — duplicate
  enqueues silently no-op. Use `True` only when the caller needs to know.
- **`lock_expiry`** is mandatory in practice. Without an expiry, a worker
  crash leaves a permanent lock. Match it to the task's `time_limit`.

> **Singleton ≠ idempotent.** Singleton prevents *overlap*, not *duplicate
> work*. If the same arguments can re-enqueue after the previous run
> finished, the task body still needs to be idempotent. The
> `SingletonAutoRescheduleFlag` pattern handles "an update arrived while
> I was running"; see `baserow.contrib.database.search.tasks` for an example.

To add a singleton task, see the [singleton recipe](../patterns/celery-tasks.md#singleton-tasks).

## Retry mechanisms

Three patterns are in use:

1. **`autoretry_for=(SomeException,)`** — declarative; Celery retries
   automatically when the named exception is raised.
2. **`self.retry(...)`** — imperative; the task explicitly retries with
   custom args / countdown.
3. **Hand-rolled exponential backoff** — when you need to surface the
   attempt number to the task body. Used by webhook delivery:
   `self.retry(countdown=2**retries, kwargs={...})`.

For Jobs specifically, retries are **not** the default story — a failed
job is a failed job, not a retry candidate. If you need retries, you
probably want a plain task, not a Job.

Recipe with three side-by-side templates: [Retry strategies](../patterns/celery-tasks.md#retry-strategies).

## Transactions and the database

The Celery app installs signal handlers in `config/celery.py` that, on
every task:

- `task_prerun`: clear thread-local caches, close stale DB connections.
- `task_postrun`: same again, plus reset.

This matches Django's guidance for long-running worker processes that
would otherwise hold dead connections after PostgreSQL recycles them.

The Job framework wraps `run` in a configurable transaction context
(`JobType.transaction_atomic_context`) — see
[Jobs > Optional hooks](jobs.md#jobtype-api-surface). For plain tasks, if
you need a specific isolation level, open `transaction.atomic()` yourself
at the top of the task body.

When enqueueing, **always** wrap with `transaction.on_commit(...)` —
otherwise the worker can race the commit. The
[enqueue-safely recipe](../patterns/celery-tasks.md#enqueue-from-a-transaction)
spells out the failure mode.

## Observability

Every task is automatically traced. `BaserowTelemetryTask` (set as
`app.Task`) attaches the task name to OpenTelemetry baggage on each call,
so spans emitted from inside the task are correctly attributed.

OTEL plumbing lives in `baserow.core.telemetry`. The worker startup hook
calls `setup_telemetry(add_django_instrumentation=False)` — Django
instrumentation is skipped on workers since there are no HTTP requests to
trace there.

Logs use `loguru` — `from loguru import logger`. Avoid
`logging.getLogger` in task code; it doesn't flow through the same sinks.

For richer progress reporting on long-running tasks, use the
[Job framework](jobs.md) — its `Progress` helper integrates with the
cache layer so the frontend can poll for `progress_percentage`. Plain
Celery tasks have no progress channel.

## Configuration env vars

The Celery-relevant variables; see
[Configuring Baserow](../installation/configuration.md) for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `CELERY_TASK_SOFT_TIME_LIMIT` | 300 | Global soft limit (seconds). |
| `CELERY_TASK_TIME_LIMIT` | 360 | Global hard limit (seconds). |
| `BASEROW_JOB_SOFT_TIME_LIMIT` | 1800 | Soft limit for `run_async_job`. |
| `BASEROW_CELERY_SEARCH_UPDATE_HARD_TIME_LIMIT` | 3600 | Search reindex hard limit. |
| `CELERY_RESULT_EXPIRES` | 3600 | How long task results survive in Redis. |
| `CELERY_BEAT_MAX_LOOP_INTERVAL` | 20 | Beat scheduler tick. |
| `CELERY_REDBEAT_LOCK_TIMEOUT` | derived | Beat coordination lock TTL. |
| `BASEROW_AMOUNT_OF_WORKERS` | unset | If set, passed as `--concurrency` to the worker. |
| `BASEROW_RUN_MINIMAL` | unset | Collapse both workers into one process. |

## Celery task vs Job — when to use which

| You want | Use |
|---|---|
| Fire-and-forget async work (emails, notifications, webhook delivery) | A [plain Celery task](../patterns/celery-tasks.md) |
| User-triggered work the user is watching, with progress + cancel | A [Job](jobs.md) (see [JobType walkthrough](../patterns/jobtypes.md)) |
| Periodic background maintenance | A [periodic task](../patterns/celery-tasks.md#periodic-tasks), maybe singleton |
| Step-by-step work the user resumes after interruption | Neither — jobs aren't resumable. Model the work yourself. |

## See also

- [Celery tasks (cookbook)](../patterns/celery-tasks.md) — the recipe side
  of this page.
- [Jobs (deep dive)](jobs.md) — the framework that sits on top of Celery.
- [JobType walkthrough](../patterns/jobtypes.md) — end-to-end how-to.
- [Systems overview](systems-overview.md) — where Celery fits on the map.
- [Observability](../patterns/observability.md) — tracing, logs, OTEL.
- [Configuring Baserow](../installation/configuration.md) — canonical env-var reference.
