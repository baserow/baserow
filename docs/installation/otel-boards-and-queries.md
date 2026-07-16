# Build OpenTelemetry boards and queries

Baserow sends operational metrics, sampled traces, and logs through OpenTelemetry. Use
metrics for counts and latency trends over all requests, and use retained traces to
diagnose individual requests.

The examples below use Honeycomb because the bundled development Collector exports to
it. Other OTLP backends can build equivalent queries from the same metric names and
attributes.

## Configure telemetry

Configure every Baserow web and Celery process that sends telemetry through the
tail-sampling Collector:

```bash
BASEROW_ENABLE_OTEL=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_TRACES_SAMPLER=always_on
OTEL_SEMCONV_STABILITY_OPT_IN=http
```

Configure the Collector separately:

```bash
HONEYCOMB_API_KEY=your-api-key
HONEYCOMB_METRICS_DATASET=baserow-metrics
```

Use the `BASEROW_OTEL_SLOW_*` settings to configure slow HTTP and Celery trace
classification, `BASEROW_OTEL_LOG_LEVEL` to control exported backend logs, and the
collector's `BASEROW_OTEL_*` settings to tune its span and per-user metric budgets. See
[Configuration](configuration.md) and the bundled Compose/Collector configuration for
the current defaults.

The bundled configuration uses the Collector Contrib distribution because it requires
the tail-sampling and `span_metrics` connectors. A custom Collector build must include
both, and its `span_metrics` version must support
`aggregation_cardinality_limit`. The bundled Collector command also enables
`processor.tailsamplingprocessor.recordpolicy`; this annotates the selected composite
policy so short dependency spans are compacted from baseline traces only.

All spans belonging to one trace must reach the same tail-sampling Collector instance.
Use trace-ID-aware routing when running multiple Collectors.

## Metric sources

Use these separate metric families:

| Question                  | Metric                                        | Unit         | Dimensions                                                                                  |
| ------------------------- | --------------------------------------------- | ------------ | ------------------------------------------------------------------------------------------- |
| Endpoint traffic          | `http.server.request.duration`                | Seconds      | Templated `http.route`, `http.request.method`, `http.response.status_code`, and error type. |
| Authenticated users       | `baserow.http.server.user.request.duration`   | Milliseconds | `user.id`, plus stable service and Collector identity.                                      |
| Workspace invitations     | `baserow.workspace.invitation.created.calls` | Count        | `user.id`, plus stable service and Collector identity.                                      |
| Celery task execution     | `baserow.celery.task.duration`                | Seconds      | Stable task name, queue, and completion state.                                              |
| Database/Redis dependency | `baserow.dependency.duration`                 | Milliseconds | Stable database system, operation, status, service, and Collector identity.                 |

The endpoint histogram covers all requests. The user histogram is generated from
authenticated HTTP server spans before tail sampling, so trace sampling does not alter
its request count or duration distribution. The Collector discards the span-metrics
calls counter because `HISTOGRAM_COUNT` provides the same sampling-independent count from this one
histogram, avoiding a second datapoint for every active user and flush interval.

The dependency histogram is also generated from matching spans before trace tail
sampling and baseline compaction. Its count and latency distribution therefore remain
sampling-independent even when a trace is not retained. It deliberately excludes statements, table
IDs, users, span names, and other high-cardinality dimensions.

The Celery histogram is emitted when a task completes, independently of trace
retention. Its histogram count is the completed-task count. Keep task arguments, IDs,
user IDs, and other unbounded values out of its dimensions.

Keep the families separate. Adding `user.id` to the endpoint metric or `http.route` to
the user metric would create a `user x endpoint x method x status` Cartesian product.
Never use a concrete URL, table ID, workspace ID, token ID, or other unbounded value as
an endpoint metric dimension.

## Honeycomb histogram fields

Honeycomb ingests these OTLP histograms as native histogram columns. Only the base
field, such as `http.server.request.duration`, exists in the dataset schema; flattened
fields such as `x.avg` or `x.p95` do not exist, and queries referencing them are
rejected. Aggregate directly on the base field:

- [`HISTOGRAM_COUNT(x)`](https://docs.honeycomb.io/investigate/query/build/#select-histogram-count-metric-field-name):
  observations in the interval, which is the request count.
- `SUM(x)`: sum of the observed values.
- `AVG(x)`: average of the observed values.
- `P50(x)`, `P95(x)`, and `P99(x)`: percentiles computed from the histogram buckets.
- `HEATMAP(x)`: the distribution over time.
- `COUNT_DATAPOINTS(x)`: ingested datapoints, which measures ingestion volume.

Plain `COUNT` counts metric events, not histogram observations, and therefore is not a
request count.

Set query granularity to the metric capture interval or a multiple of it.

## Endpoint board

Build these queries in `HONEYCOMB_METRICS_DATASET`:

| Panel                     | Query                                                                                                 |
| ------------------------- | ----------------------------------------------------------------------------------------------------- |
| Requests per endpoint     | `HISTOGRAM_COUNT(http.server.request.duration)` grouped by `http.route`.                              |
| Requests per method       | `HISTOGRAM_COUNT(http.server.request.duration)` grouped by `http.request.method`.                     |
| Requests per status       | `HISTOGRAM_COUNT(http.server.request.duration)` grouped by `http.response.status_code`.               |
| Average endpoint duration | `AVG(http.server.request.duration)` grouped by `http.route`.                                          |
| Endpoint p50, p95, or p99 | `P50/P95/P99(http.server.request.duration)` grouped by `http.route`.                                  |
| Endpoint duration heatmap | `HEATMAP(http.server.request.duration)`, filtered by `http.route` to focus on one route.              |
| Top endpoints             | `HISTOGRAM_COUNT(http.server.request.duration)` grouped by `http.route`, ordered descending.          |
| Server errors by endpoint | Filter `http.response.status_code >= 500`, then count histogram observations grouped by `http.route`. |

Use only templated routes such as `/api/database/rows/table/{table_id}/`. If
`http.route` contains a concrete identifier, fix that instrumentation before using it
as a board dimension.

## Per-user board

Build these queries in the same metrics dataset:

| Panel                            | Query                                                                                                                                                                        |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Requests per user                | `HISTOGRAM_COUNT(baserow.http.server.user.request.duration)` grouped by `user.id`, where `otel.metric.overflow != true`.                                                     |
| Distinct active users            | `COUNT_DISTINCT(user.id)` where `baserow.http.server.user.request.duration` exists and `otel.metric.overflow != true`.                                                       |
| Average duration per user        | `AVG(baserow.http.server.user.request.duration)` grouped by `user.id`.                                                                                                       |
| Per-user p50, p95, or p99        | `P50/P95/P99(baserow.http.server.user.request.duration)` grouped by `user.id`.                                                                                               |
| Per-user duration heatmap        | `HEATMAP(baserow.http.server.user.request.duration)` filtered by `user.id`.                                                                                                  |
| Average concurrent load per user | `SUM(baserow.http.server.user.request.duration)` grouped by `user.id`, divided by the result-bucket width in milliseconds. This is average load, not exact peak concurrency. |
| Cardinality overflow             | `HISTOGRAM_COUNT(baserow.http.server.user.request.duration)` where `otel.metric.overflow = true`; alert when non-zero.                                                       |
| Per-user metric ingestion volume | `COUNT_DATAPOINTS(baserow.http.server.user.request.duration)` to measure the cost of the selected interval.                                                                  |

The per-user metric includes authenticated requests only. Requests aggregated into an
overflow row remain visible in overall counts, but their individual users cannot be
identified.

To alert on invitation abuse, sum
`baserow.workspace.invitation.created.calls` over the trigger window, group by
`user.id`, exclude `otel.metric.overflow=true`, and alert when any user exceeds the
chosen limit. The counter records successful invitation creation and resend operations
without depending on trace retention or an HTTP route.

The `otel.metric.overflow` column appears in the dataset schema only after the first
overflow datapoint is ingested, and Honeycomb drops query filters on columns missing
from the schema. Until then the overflow filters cannot be saved and are unnecessary,
because no overflow rows exist. Add the filters and the overflow alert as soon as the
column appears.

## Database and Redis board

Build these queries from `baserow.dependency.duration` in the metrics dataset. During
semantic-convention transitions, group by the populated stable attribute
(`db.system.name` or `db.operation.name`) and fall back to its legacy counterpart
(`db.system` or `db.operation`) when needed.

| Panel                         | Query                                                                                                                 |
| ----------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Dependency calls by system    | `HISTOGRAM_COUNT(baserow.dependency.duration)` grouped by `db.system.name` (or `db.system`).                          |
| Dependency calls by operation | `HISTOGRAM_COUNT(baserow.dependency.duration)` grouped by `db.operation.name` (or `db.operation`).                    |
| Average dependency duration   | `AVG(baserow.dependency.duration)` grouped by database system and operation.                                          |
| Dependency p95 or p99         | `P95/P99(baserow.dependency.duration)` grouped by database system and operation.                                      |
| Dependency duration heatmap   | `HEATMAP(baserow.dependency.duration)`, filtered to one database system or operation.                                 |
| Dependency errors             | Filter to error status, then `HISTOGRAM_COUNT(baserow.dependency.duration)` grouped by database system and operation. |

As with request histograms, plain `COUNT` counts exported metric datapoints rather than
dependency calls. Use `HISTOGRAM_COUNT` for call volume.

## Celery task board

Build these queries from `baserow.celery.task.duration` in the metrics dataset:

| Panel                    | Query                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------ |
| Completed tasks by name  | `HISTOGRAM_COUNT(baserow.celery.task.duration)` grouped by `task_name`.                                |
| Completed tasks by queue | `HISTOGRAM_COUNT(baserow.celery.task.duration)` grouped by `queue`.                                    |
| Average task duration    | `AVG(baserow.celery.task.duration)` grouped by `task_name` and optionally `queue`.                     |
| Task p95 or p99          | `P95/P99(baserow.celery.task.duration)` grouped by `task_name`.                                        |
| Task duration heatmap    | `HEATMAP(baserow.celery.task.duration)`, filtered to one task or queue.                                |
| Failed task completions  | Filter `state = FAILURE`, then `HISTOGRAM_COUNT(baserow.celery.task.duration)` grouped by `task_name`. |

Use the scheduled-task counter separately when the distinction between published and
completed tasks matters. Do not infer task volume from sampled traces.

## Control per-user metric volume

`BASEROW_OTEL_USER_METRICS_FLUSH_INTERVAL` controls resolution and datapoint volume. A
shorter interval produces finer charts and more datapoints for continuously active
series.

`BASEROW_OTEL_USER_METRICS_CARDINALITY_LIMIT` is a per-Collector circuit breaker for
unique metric dimension combinations. Once reached, new combinations are aggregated
under `otel.metric.overflow=true` instead of increasing series cardinality without a
bound. `BASEROW_OTEL_USER_METRICS_SERIES_EXPIRATION` removes a user's series after the
configured idle period, preventing historical users from remaining in every subsequent
export.

Choose the limit above the measured peak unique users within the series-expiration
window, leave headroom for multiple services and resource scopes, and alert on
overflow. When using multiple Collectors, group by `user.id` without grouping by
`collector.instance.id` so the query combines a user's observations from every
Collector.

## Investigate retained traces

The bundled Collector receives complete candidate traces and makes one tail-sampling
decision for the whole trace. Explicitly forced traces bypass the normal bounded
budget. Within that budget, errors and configured slow HTTP/Celery traces are
prioritized before representative baseline traffic. Error and slow traces can still be
dropped when their allocated capacity is exhausted. Baseline traces may have noisy
dependency detail compacted; all-traffic dependency counts and latency remain available
from `baserow.dependency.duration`.

Application spans form a semantic skeleton rather than mirroring every Python call. An
HTTP trace contains its request root, one concrete API view entry point such as
`GridViewView.get`, one outermost action/job or selected domain operation, and at most
one level of explicitly important phases such as permission evaluation or cache-miss
model generation. Every Celery execution starts a new task trace linked to the trace
that published it, then uses the task root followed by the same operation/phase levels.
Automatic database, Redis, and outbound HTTP spans remain children of their
nearest semantic span. Selected framework siblings show time outside the view without
tracing every middleware; for example, `DRFResponse.render` measures response
serialization.

For a specific request, add this backend query parameter:

```text
?force_full_otel_trace=true
```

The SDK and Collector recognize the marker, and the Collector retains that complete
trace outside the normal error, slow-request, and baseline budget.

Useful trace queries include:

- Root spans with error status for request-level failures.
- `baserow.http.request.slow=true` for requests above the configured threshold.
- `baserow.celery.task.slow=true` for tasks above their configured threshold and not
  running on an excluded queue.
- `baserow.force_full_otel_trace=true` for explicitly requested traces.
- A known trace ID when moving from an application error or log to its trace.

Do not use retained trace counts as request, user, error, or action counts. The sampling
policies deliberately retain different classes of traffic at different rates.

## Coverage limits

The current metrics intentionally do not preserve every possible trace grouping:

- User and endpoint metrics are separate. They do not answer `user.id x http.route`
  questions over all traffic.
- Duration sums provide average concurrent load, not the exact overlap or peak
  concurrency waveform.
- Per-user SQL time is available on retained traces, not as an all-traffic metric.
- Exact action counts other than workspace invitation creation, exception-type trends,
  and rate-limit reasons require their own bounded counters or histograms.

Add a purpose-built metric only after defining its allowed dimensions and cardinality
budget. For billing, quotas, abuse controls, or contractual usage reporting, use a
durable usage-accounting pipeline rather than best-effort OTLP metrics.

## Validation checklist

- Endpoint metric counts match an independent request source within export delay.
- `http.route` values are templates and contain no concrete identifiers.
- Per-user request counts match an independent source while overflow is zero.
- Per-user workspace invitation counts match successful creation and resend operations.
- An alert exists for `otel.metric.overflow=true`.
- Query granularity is the capture interval or a multiple of it.
- Error, slow, and forced traces preserve dependency detail when retained.
- Baseline traces preserve the semantic application path.
- `?force_full_otel_trace=true` produces a retained complete trace.
- Collector refused data and export-failure metrics are monitored.

For application and Collector setup, see
[Monitoring your Baserow server](monitoring.md). For instrumentation conventions, see
[Working with metrics and logs as a developer](../development/metrics-and-logs.md).
