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
