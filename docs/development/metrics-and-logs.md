# Working with metrics and logs as a developer

First see [our monitoring doc](../installation/monitoring.md) for an overview what
Baserow offers to monitor itself.

This doc explains how to:

1. Setup your dev environment so you can monitor it, find performance
   issues etc
2. Add new logs to the codebase and when to do so
3. What tracing is and how to add new spans tracing your functions
4. Add new metrics to the codebase and when to do so

## Setting up honeycomb to view Baserow telemetry in your local dev env

1. Sign up at https://honeycomb.io.
2. Create your own environment inside of honeycomb, you will configure your local dev
   setup to send events here.
3. Click on your new environment in the sidebar, click the config icon.
4. Switch to API keys and copy your API key.
5. Edit your local `.env` and set:

```bash
HONEYCOMB_API_KEY=YOUR_KEY
BASEROW_ENABLE_OTEL=true
```

6. Restart the dev environment:
    ```bash
    just dc-dev restart
    ```
7. Go to your honeycomb environment and you should start seeing new datasets being
   created!

### Debugging telemetry

Look at the logs of your otel-collector for a starting place:

```
docker logs baserow-otel-collector-1
```

### Under the hood

- `docker-compose.dev.yml` also launches
  an [Open Telemetry Collector](https://opentelemetry.io/docs/collector/) service
  configured by the file in `deploy/otel/otel-collector-config.yaml`.
- When you enable telemetry using `BASEROW_ENABLE_OTEL=true` the dev containers are
  configured by the
  `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318` in `docker-compose.dev.yml`
  to send telemetry to that local collector.
- Then this local collector will send telemetry
  to [honeycomb](https://honeycomb.io) using your `HONEYCOMB_API_KEY` where you can
  finally inspect everything.

## How to log

To log something just:

```
from loguru import logger

def application_code():
   logger.info('something')
```

See [Loguru's docs](https://github.com/Delgan/loguru) for more information, it has a ton
of awesome features.

### When and what to log

Use `loguru` for useful, structured application logs that help diagnose what happened
without emitting one log for every item in an unbounded operation.

1. Log for humans, so they can diagnose what happened in Baserow.
2. Use the different logging levels available to you error/warning/info/debug/trace.
3. Avoid logging once per row, field, or other item in an unbounded loop. Prefer one
   structured summary log and metrics for counts.
4. `BASEROW_OTEL_LOG_LEVEL` can keep verbose local logs while exporting only warning
   and error logs through OTLP.

## How add spans to trace requests and method performance

Read [this](https://opentelemetry.io/docs/concepts/observability-primer/#distributed-traces)
first to understand what a trace and span is and why we want them.

### Tracing a function

You can use the helper decorator `baserow_trace` to wrap a function
in a span to track its execution time and other attributes:

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)


class SomeClass:
    @baserow_trace(tracer)
    def my_func(
            self
    ):
        # do expensive operation we want to track how long it takes
        pass
```

`@baserow_trace` will:

1. Wrap the function in a span
2. Set the span name to the function's qualified name automatically
3. Catch errors and mark the span as failed and register the exception against the span
   so it gets sent to the collector.

Every DRF request automatically receives one concrete API entry span such as
`GridViewView.get` below the HTTP server span. Nested functions wrapped by
`@baserow_trace` then run inside the outermost decorated domain operation, so a handler
calling other decorated handlers does not produce one span per Python call.
Automatic database, Redis, HTTP, and other instrumentation still creates child spans,
so expensive external work remains visible. A small number of important phases, such
as permission evaluation and cache-miss model generation, can use
`@baserow_trace(tracer, allow_nested=True)`. The resulting maximum application-owned
hierarchy is API entry point, domain operation, then important phase; further decorated
calls at the same or a lower semantic level collapse.

Celery auto-instrumentation creates a separate consumer trace for each task execution
and links it to the trace that published the task. The first selected
`@baserow_trace` domain method becomes the principal operation under that task root;
nested selected handlers collapse in the same way as HTTP operations. Do not add a
second generic span around the whole task body because it duplicates the task root.
Decorate the principal job, export, workflow, or cleanup method instead.

Framework work outside the view is represented by a small number of sibling phases
rather than one span for every middleware. `DRFResponse.render` shows response
serialization and rendering after the view returns. When Silk is enabled in the
development environment, `Silk.persist_profile` shows the profiler finalizing and
persisting its own request data. Silk's internal database writes are suppressed from
dependency instrumentation because the single phase duration is the useful signal.
This distinction matters when a Django request root is much longer than its API view:
the remainder can be framework or development-profiler work rather than application
handler time.

### Tracing selected methods in a class

Put `@baserow_trace` directly on each selected method. The instrumentation then moves
with the method when it is renamed, and adding or renaming an unrelated helper cannot
silently change the trace shape.

```python
from opentelemetry import trace
from baserow.core.telemetry.utils import baserow_trace

tracer = trace.get_tracer(__name__)


class SomeClass:
    @baserow_trace(tracer)
    def run_operation(self):
        pass

    @baserow_trace(tracer, allow_nested=True)
    def check_permissions(self):
        pass

    def implementation_helper(self):
        # This method is deliberately not traced.
        pass
```

### Tracing overridden contract methods

For an abstract or polymorphic contract such as `ActionType` or `JobType`, use
`BaserowTraceMeta` and decorate the base method. The metaclass propagates that trace
configuration to every override, so concrete implementations do not need another
decorator and their qualified method name is still used for the span.

```python
import abc
from opentelemetry import trace
from baserow.core.telemetry.utils import BaserowTraceMeta, baserow_trace

tracer = trace.get_tracer(__name__)


class ActionType(metaclass=BaserowTraceMeta):
    @classmethod
    @baserow_trace(tracer)
    @abc.abstractmethod
    def do(cls):
        # Every subclass override of `do` is traced automatically.
        pass
```

Prefer one action, job, workflow, or expensive query boundary. Do not instrument
getters, serializers, constructors, signal receivers, or every step of handler
choreography. Add a nested phase only when it answers a recurring performance question
that automatic dependency spans cannot answer.

### Adding attributes to the current span

Its often very useful to add attributes to the current span so we can filter and query
by those later when inspecting the telemetry. We have a simple helper function
that lets you do this:

```python
        add_baserow_trace_attrs(
    attr_you_want_on_the_span=value_you_want,
    other_attr=other_value
)
```

Or you can just use the default OTEL methods:

```python
    span = get_current_span()
span.set_attribute(f"baserow.my_span_attr", value)
```

### Using the OTEL API directly

Remember you can also just manually use
the [OTEL Python API](https://opentelemetry.io/docs/languages/python/instrumentation/#traces).
The helper functions
shown above are just to help you.

## How to track metrics

You can also keep track of various numerical and statistical metrics using open
telemetry. We don't provide any helper methods as the otel functions are
straight-forward.
Read [this](https://opentelemetry.io/docs/languages/python/instrumentation/#metrics)
for all of the available types of metrics you can use, but a simple example is shown
below:

> Important: Any attributes you add to metric will result in a brand-new event being
> send per periodic metric send for that specific combination of metric and attributes.
> You must make sure that any attributes added will have only a constant possible number
> of values and a small number of them. This is to prevent an ever-increasing number of
> metric events being sent to the server.
>
> For example, below if we called `counter.add(1, {"table_id":table.id})` OTEL will
> send a metric data point for every single table it has seen **every single sync**
> resulting in an ever-increasing number of metric events being sent. However, if instead
> the attribute we added was something like "bulk_created": True or False this is fine
> as there are only two possible values.

```python
from opentelemetry import metrics

meter = metrics.get_meter(__name__)
rows_created_counter = meter.create_counter(
    "baserow.rows_created",
    unit="1",
    description="The number of rows created in user tables.",
)

def create_row(table):
    # create some row
    # keep track of how many have been made!
    rows_created_counter.add(
        1
    )

```

## Complete traces with bounded tail sampling

Use [Build OpenTelemetry boards and queries](../installation/otel-boards-and-queries.md)
for the supported endpoint and per-user metrics, Honeycomb queries, and retained-trace
investigations.

The bundled development collector makes one sampling decision for the complete trace.
It prioritizes errors and HTTP/Celery traces carrying their respective slow markers,
then uses bounded span throughput for representative normal traces. Queues expected to
run for a long time can be excluded from duration-based task marking.

All Baserow processes sending to that collector must use the same always-on SDK sampler:

```bash
OTEL_TRACES_SAMPLER=always_on
```

Do not sample Django root spans separately from database, Redis, Celery, or application
spans. Per-instrumentation sampling creates root-only and otherwise fragmented traces.

To retain one specific complete trace regardless of the bounded sampling budget, add
the explicit escape-hatch query parameter to the backend request:

```text
?force_full_otel_trace=true
```

The request span is marked with `baserow.force_full_otel_trace=true`, and the tail
sampler retains the whole trace before evaluating its bounded policies. The one global
SDK sampler also recognizes this query before making its sampling decision.

Configure the collector's total span budget and policy allocation in
`deploy/otel/otel-collector-config.yaml`. When running multiple collectors, divide the
budget between them and use trace-ID-aware routing so every span in a trace reaches the
same tail sampler.

The Collector also forks authenticated HTTP root spans before tail sampling and emits
`baserow.http.server.user.request.duration`. This histogram has `user.id` as its only
request dimension; endpoint analytics continue to use
`http.server.request.duration`. Keep the two families separate so user cardinality is
not multiplied by route, method, and status.

Successful workspace invitation creation and resend operations emit a short-lived
metric observation span. The Collector converts it into the bounded
`baserow.workspace.invitation.created.calls` counter, dimensioned only by `user.id`,
then removes the observation span from retained traces.

Completed Celery tasks emit `baserow.celery.task.duration` with bounded `task_name`,
`queue`, and `state` dimensions. Use its histogram count and distribution for sampling-independent
task volume and latency boards instead of counting sampled task traces.

Database and Redis spans are also forked before trace sampling into sampling-independent,
low-cardinality `baserow.dependency.duration` histogram. Its observation count and
duration distribution remain accurate when the corresponding trace is not retained.
Only stable database system and operation attributes are dimensions; never add
statements, table IDs, URLs, or user IDs to this metric.

The per-user metric family uses bounded cardinality and reports overflow through
`otel.metric.overflow=true`. Tune its limit, flush interval, and idle expiration with
the documented `BASEROW_OTEL_USER_METRICS_*` collector variables, and alert on
overflow.
