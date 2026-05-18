# Progress bars

Job progress is visible while the job is still running because Baserow mirrors
progress to Redis. Database writes inside a job transaction are not visible to
other connections until commit; Redis is the live side channel.

For the full Job framework see [Jobs](../technical/jobs.md).

## Lifecycle

```
JobType.run(job, progress)
  -> progress.set_progress(N)
  -> JobHandler progress callback
  -> job.set_cached_state()
  -> Redis stores state/progress
  -> frontend polls /api/jobs/
  -> serializer reads cache before DB
  -> Vuex job store updates progress UI
```

There is a websocket event when a job starts. There is no websocket event for
every progress tick; progress is polled.

## Backend Contract

`JobType.run(job, progress)` should call:

- `progress.set_progress(N)` at meaningful checkpoints.
- `progress.increment(...)` for simple counters.
- `progress.create_child(represents_progress=..., total=...)` for multi-step
  work.

Every progress update:

1. Updates the in-memory job state.
2. Writes state/progress to Redis.
3. Checks whether the job was cancelled.

Do not set `job.progress_percentage` manually. Use `Progress`.

## Cache Contract

`Job.set_cached_state()` writes a dict with `state`, `progress_percentage`, and
`updated_on`. Job serializers should read through cache-aware getters such as
`get_cached_progress_percentage()` and `get_cached_state()`.

The DB remains the durable terminal state. Redis is the live view while the job
runs.

## Frontend Contract

`web-frontend/modules/core/store/job.js` owns polling:

- On app load, it fetches unfinished jobs.
- On `job_started`, it adds the job and starts polling.
- Polling batches active job ids into one request.
- The interval backs off and stops when all jobs are terminal.

A backend job type needs a matching frontend `JobType` registered in the `job`
registry. Without it, the job may run but not render in the sidebar.

For component wiring see [Adding a new job type](jobtypes.md).

## Deprecated Mixin

`web-frontend/modules/core/mixins/jobProgress.js` is the older single-job polling
pattern. New code should use the Vuex job store and `mixin/job`.

## Anti-Patterns

- Updating `job.progress_percentage` without `Progress`.
- Reading raw DB progress in serializers for in-flight jobs.
- Pushing progress ticks over websocket.
- Polling from a component with a fixed `setInterval`.
- Forgetting the frontend `JobType` registration.
- Reporting progress too rarely for cancellation to be noticed.

## Checklist

- [ ] `run` calls `progress.set_progress(...)` or child progress regularly.
- [ ] Serializers use cache-aware state/progress getters.
- [ ] Frontend `JobType` is registered.
- [ ] Job store, not component-local polling, owns updates.
- [ ] Cancellation is tested for long-running loops.

## Related

- [Jobs](../technical/jobs.md).
- [Celery](../technical/celery.md).
- [Caching](../technical/caching.md).
- [JobType walkthrough](jobtypes.md).
