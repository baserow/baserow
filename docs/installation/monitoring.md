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

`BASEROW_OTEL_SLOW_REQUEST_THRESHOLD_SECONDS` controls the slow-request marker and
`BASEROW_OTEL_SLOW_CELERY_TASK_THRESHOLD_SECONDS` controls the task marker for every
queue. Task errors remain eligible for error retention regardless of duration.
`BASEROW_OTEL_LOG_LEVEL` separately controls OTLP log volume without changing local
backend logging. See [Configuration](configuration.md) for current defaults.

### Retain every eligible trace

Lower-traffic installations can retain every eligible trace by keeping
`OTEL_TRACES_SAMPLER=always_on` and setting:

```bash
BASEROW_OTEL_TAIL_SAMPLING_MAX_SPANS_PER_SECOND=-1
```

This selects an always-sample tail policy and retains complete traces, not only root
spans. Deliberately filtered low-value telemetry, such as routine `OPTIONS`/`HEAD`
requests, successful Redis idle waits, and internal metric observations, remains
excluded. Use a positive value to restore bounded priority sampling.

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
