# Monitoring your Baserow server

Baserow can be configured to ship logs, metrics and traces using
the [Open Telemetry standard](https://opentelemetry.io/). You can use these to monitor
your Baserow instance.

Enable this by setting the env var `BASEROW_ENABLE_OTEL=true` and then depending on
where you want to send telemetry set the
appropriate [OTEL env vars](https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/).
You probably want to set `OTEL_EXPORTER_OTLP_ENDPOINT` also.

The Docker Compose files pass through the OTLP endpoint, resource attributes, trace
sampler, trace sampler argument, HTTP semantic-convention selection, OTLP log level,
and slow HTTP/Celery threshold settings.

By default, Baserow will send the following telemetry:

- Baserow application logging.
- Some basic metrics.
- Various spans over some of our critical functions and handler methods.
- Automatic instrumentation provided by OTEL libraries for:
    - S3 usage by the `botocore` library
    - SQL queries
    - Redis queries
    - HTTP queries
    - Celery tasks
    - Django requests/responses

## Request counts and trace sampling

For ready-to-use endpoint, per-user, cardinality, and trace queries, see
[Build OpenTelemetry boards and queries](otel-boards-and-queries.md).

Use metrics, rather than retained trace counts, for traffic and latency boards:

- `http.server.request.duration` provides request counts and latency by templated
  endpoint, method, and response status.
- `baserow.http.server.user.request.duration` provides authenticated request counts and
  latency by `user.id` without multiplying user cardinality by endpoint dimensions.
- `baserow.workspace.invitation.created.calls` counts successful invitation creation
  and resend operations by the acting `user.id`.
- `baserow.celery.task.duration` provides completed task counts and latency by stable
  task, queue, and state.
- `baserow.dependency.duration` provides database and Redis call counts and latency by
  stable system and operation attributes.

These metric families are produced independently of trace retention. Keep their
dimensions bounded: do not add raw URLs, table IDs, workspace IDs, task arguments, or
other unbounded values. The per-user family has configurable cardinality, flush, and
idle-expiration controls and reports overflow through `otel.metric.overflow=true`.

This per-user metric is suitable for operational boards, but best-effort OTLP delivery
is not a billing or quota ledger. Use a durable usage-accounting pipeline where missing
a request is unacceptable.

Head sampling cannot discover that a request was slow or failed after it has started.
To retain useful traces while controlling export volume:

1. Configure every Baserow process with `OTEL_TRACES_SAMPLER=always_on` so the local
   collector receives complete traces.
2. Configure a tail-sampling Collector to prioritize spans with `ERROR` status and
   spans marked as slow HTTP requests or Celery tasks.
3. Give ordinary traces the remaining bounded throughput.

Add `?force_full_otel_trace=true` to a backend request when you need its complete trace
regardless of the bounded sampling budget. Baserow marks that trace explicitly so the
collector can retain it before applying the normal error, slow-trace, and baseline
policies. The global SDK sampler recognizes the same marker before making its sampling
decision. When that request publishes a Celery task, the marker is propagated to the
task's independently sampled trace.

The query parameter is an operational escape hatch, not an authorization mechanism.
Any caller that can reach the endpoint can set it, and the bundled Collector exempts
forced traces from its normal sampling and span-pruning budgets. On an internet-facing
installation, restrict or rate-limit this parameter at the reverse proxy, or put forced
traces under a Collector-side budget. Downstream ingestion limits remain the final
cost-control backstop.

`BASEROW_OTEL_SLOW_REQUEST_THRESHOLD_SECONDS` controls the slow-request marker and
`BASEROW_OTEL_SLOW_CELERY_TASK_THRESHOLD_SECONDS` controls the task marker for every
queue. Task errors remain eligible for error retention regardless of duration.
`BASEROW_OTEL_LOG_LEVEL` separately controls OTLP log volume without changing local
backend logging. See [Configuration](configuration.md) for current defaults.

The bundled Collector waits up to `BASEROW_OTEL_TAIL_SAMPLING_DECISION_WAIT` (`5m` by
default) for a trace root. After the completed root arrives, it waits only
`BASEROW_OTEL_TAIL_SAMPLING_DECISION_WAIT_AFTER_ROOT_RECEIVED` (`5s` by default) before
deciding. Ordinary HTTP traces are therefore normally held for their request duration
plus this short grace period, not for five minutes. Long-running Celery traces remain
eligible for completion-based error and slow-trace policies until the maximum wait.

Every inbound HTTP request starts an independently sampled Baserow trace. When a request
contains upstream trace context, the Baserow root links to that remote span instead of
becoming its child. The link preserves navigation between the traces while ensuring the
Collector can always recognize the completed Baserow request as a root and apply the
short post-root grace period.

Queued Celery tasks consume no trace-buffer space. Running tasks consume space only
after they emit a span, and normally leave the buffer shortly after their root arrives.
The steady-state requirement is therefore approximately active rootless task traces
plus the incoming HTTP trace rate multiplied by the root-arrival grace period, with
headroom for bursts and orphaned traces. Span-heavy tasks can still exhaust the 512 MiB
memory limit before the `num_traces: 100000` count is reached. Monitor
`otelcol_processor_tail_sampling_sampling_trace_dropped_too_early` and
`otelcol_processor_tail_sampling_sampling_trace_removal_age`, and shorten the maximum
wait or use a dedicated Celery sampling pipeline if long-running task traces cause
pressure.

### Retain every eligible trace

Lower-traffic installations can retain every eligible trace by keeping
`OTEL_TRACES_SAMPLER=always_on` and setting:

```bash
BASEROW_OTEL_TAIL_SAMPLING_MAX_SPANS_PER_SECOND=-1
```

This selects an always-sample tail policy and retains complete traces, not only root
spans. Deliberately filtered low-value telemetry, such as routine `OPTIONS`/`HEAD`
requests, successful Redis idle waits, and internal metric observations, remains
excluded. Parentless Redis, outbound HTTP, Silk, handler, and other implementation
spans are also rejected by the SDK instead of becoming isolated traces. Use a positive
value to restore bounded priority sampling.

Set `OTEL_SEMCONV_STABILITY_OPT_IN=http` to emit the stable
`http.server.request.duration` histogram with templated `http.route`,
`http.request.method`, and `http.response.status_code` attributes. The Docker Compose
configuration selects this mode by default.

The development collector in `deploy/otel/otel-collector-config.yaml` is an example. Its
span budget and per-user metric controls are configurable through the corresponding
`BASEROW_OTEL_*` environment variables in `docker-compose.dev.yml`.

Retained error and slow traces keep their dependency detail. Baseline traces form a
compact skeleton: request root, concrete API view entry point, one action/job or
selected domain operation, important phases such as permission checks or model
generation, selected framework phases such as `DRFResponse.render`, and meaningful
dependencies. Each Celery execution starts an independently sampled task trace linked
to its producer trace, then uses the same operation/phase structure. This keeps a long
task from depending on an earlier HTTP trace decision while preserving navigation back
to the publisher. The collector may compact noisy dependency detail from baseline
traces without changing the all-traffic dependency metrics. Forced traces bypass the
normal sampling budget and baseline compaction.

In a collector cluster, route all spans sharing a trace ID to the same tail-sampling
instance; otherwise the sampler cannot make a decision over the complete trace.

## WebSocket and realtime metrics

WebSocket metrics are independent of trace sampling. Group them by deployment or pod
and `process.pid`: an aggregate can hide one blocked ASGI worker. These metrics use
bounded operation/outcome labels and exclude JWTs, payloads, user/table IDs, and
client-supplied WebSocket IDs. See [WebSocket concurrency and replay](../technical/websockets.md)
for the execution and recovery model.

| Metric | Interpretation |
| --- | --- |
| `baserow.websocket_phase_duration` | Milliseconds for `handshake` (application arrival to accept), `authentication`, `connect`, `accept`, `replay_cursor`, and `replay_query`, by outcome. Count `phase=handshake,outcome=accepted` observations for accepted handshakes per worker. |
| `baserow.websocket_handshakes_pending` | Applications that arrived but have not accepted or rejected. |
| `baserow.websocket_sync_queue_duration` / `baserow.websocket_sync_execution_duration` | Milliseconds before the executor starts work versus milliseconds on its thread, including database connection cleanup. |
| `baserow.websocket_sync_pending` / `baserow.websocket_sync_executing` | Awaiting callers, including queued and running calls, versus work actually executing. Executing work can outlive a cancelled caller. |
| `baserow.websocket_event_loop_lag` | Scheduling delay in milliseconds, sampled once per second while WebSocket applications are active. |
| `baserow.websocket_replay_requests` | Decisions by `baseline`, `replayed`, `refresh`, `overloaded`, `deadline_exceeded`, `query_timeout`, `database_error`, `cancelled`, or `error`. Refresh `reason` distinguishes `missing_cursor`, `unknown_history`, `cursor_ahead`, `expired_payload`, and `event_limit`; other outcomes use `none`. |
| `baserow.websocket_replay_duration` / `baserow.websocket_replay_events` | Caller wait in milliseconds and number of events returned by a completed decision. |
| `baserow.websocket_replay_inflight` / `baserow.websocket_replay_capacity` | Occupied slots and initialized replay pool capacity, including work still running after cancellation or a deadline. |
| `baserow.websocket_replay_queued` / `baserow.websocket_replay_queue_capacity` / `baserow.websocket_replay_queue_duration` | Waiting requests, admission queue capacity, and wait in milliseconds, including cancelled/expired waits. Admission precedes the separate synchronous executor queue measurement. |
| `baserow.websocket_replay_database_errors` | Database errors by reason, including errors occurring after the caller's deadline. |
| `baserow.realtime_recording_events` | Attempted recording envelopes by `destination=users/page` and handler `outcome=success/error`. A successful handler does not guarantee an enclosing transaction committed. |
| `baserow.realtime_recording_batch_size` / `baserow.realtime_recording_duration` | Envelopes per attempted batch and handler duration in milliseconds, including adaptation and database work. |
| `baserow.realtime_cleanup_deleted` / `baserow.realtime_cleanup_batch_size` | Deleted events and rows per successfully committed cleanup batch. |
| `baserow.realtime_cleanup_batch_duration` | Batch duration in milliseconds, including expired-history summary updates and commit. Failed batches have `outcome=error` and contribute no deleted rows. |
| `baserow.realtime_cleanup_run_deleted` / `baserow.realtime_cleanup_run_duration` | Committed progress and run duration in milliseconds, by outcome. Earlier commits still count if a later batch fails. |
| `baserow.realtime_cleanup_skipped` | Scheduled attempts skipped for `reason=overlap` (another task owns the lease) or `reason=lock_error` (lease acquisition failed). |

Synchronous operations distinguish `authentication`, `page_permission`,
`presence_space`, `recording`, and `replay`. `executor=thread_sensitive` denotes the
shared thread in ordinary WebSocket scopes; a synchronous Celery caller can instead
use its task thread. `executor=isolated` identifies replay's separate executor.
`presence_space` measures page-type resolution, including public-view queries.
Database-free dispatch makes no cleanup submission. Channels' final disconnect
cleanup is retained but is not included in these operation metrics.

Compare queue and execution time for each operation on each worker. Long execution
identifies work occupying a thread; queue delays show its waiting callers. High
event-loop lag points to synchronous work on the loop, CPU starvation, or process
resource pressure instead. During cancellation, pending and executing are not a
strict subtraction for queue length. Replay has its own explicit queued metric.

Duration histograms contain completed observations. Pending gauges help expose work
that has not finished. Slow operations log warnings after one second, rate-limited
per phase and operation to one every 30 seconds per process. Debug phase logs use a
server-generated connection correlation ID. Event-loop lag becomes observable only
after the loop responds again; worker stacks and database wait events help diagnose
a complete stall. These instruments add no diagnostic database queries.

### Capacity and storage interpretation

Replay capacity appears only after a worker initializes its pool; importing the
module in another process does not add capacity. Compare occupancy, queued work,
overloads, and deadline outcomes per initialized worker, and use configured ASGI
worker counts when sizing a deployment. For steady traffic, estimate utilization
as request rate multiplied by mean thread execution time divided by replay
concurrency. Caller latency understates demand when work continues after a timeout,
and averages do not predict reconnect bursts.

Potential replay database connections scale as pods × ASGI workers per pod × replay
concurrency, in addition to HTTP, authentication, Celery, and other database users.
Keep this total within the database or pool budget. A result-size limit and async
deadline do not bound recording writes or terminate blocked connection attempts.

The handshake timer starts when the application is invoked and excludes proxy
waiting. Correlate it with ingress attempts, upstream selection and timings; HTTP
health checks alone do not establish WebSocket responsiveness. Channel-capacity
warnings describe full recipient queues, not a connection limit or proof that Redis
has exhausted memory.

Compare recording rate with committed cleanup deletions over time. A cleanup run
ending with `budget` retained its earlier commits but exhausted its time allowance;
`success` can still leave locked rows for the next run. Repeated overlap or lock
errors explain runs that never reached the database. Track oldest full-event age,
event-table size, history-summary count and size,
`pg_stat_user_tables` live/dead tuple estimates and vacuum/analyze timestamps, and
database I/O alongside these metrics. Deletion and vacuum make space reusable;
they do not normally reduce allocated table files. Replay refresh fallbacks also
create HTTP reads, so include that traffic when assessing capacity.

Cleanup deletes expired business payloads while preserving routing summaries for
exact audiences. Summaries have no fixed size bound: distinct audiences can
accumulate, although new ignored sockets alone do not create additional rows.
Measure summary growth alongside recent event volume and cleanup progress.

For users-channel replay, compare rows and heap blocks visited with events actually
returned. Recipient selection should use `target_user_ids` and `all_users`, with
`ws_realtime_targets_idx` and `ws_realtime_all_users_idx` available to the planner.
There is no full-payload GIN index. Include recipient-trigger work in recording
measurements; smaller indexes do not by themselves guarantee faster inserts.

Refresh reasons separate storage coverage from event volume: `expired_payload`
means relevant missed history was compacted or falls outside the replay window;
`unknown_history` means the cursor predates the known history boundary after
activation or reset; `event_limit` means too many replayable changes remain.
