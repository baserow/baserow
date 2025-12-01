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

6. `./dev.sh restart`
7. Go to your honeycomb environment and you should start seeing new datasets being
   created!

### Debugging telemetry

Look at the logs of your otel-collector for a starting place:

```
docker logs baserow-otel-collector-1
```

### Under the hood

* `docker-compose.dev.yml` also launches
  an [Open Telemetry Collector](https://opentelemetry.io/docs/collector/) service
  configured by the file in `deploy/otel/otel-collector-config.yaml`.
* When you enable telemetry using `BASEROW_ENABLE_OTEL=true` the dev containers are
  configured by the
  `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318` in `docker-compose.dev.yml`
  to send telemetry to that local collector.
* Then this local collector will send telemetry
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

As of Feb 2023 Baserow doesn't log that much. Now we have a nicer logging framework
`loguru` and a way of shipping and storing logs using OTEL we should log much more.

1. Log for humans, so they can diagnose what happened in Baserow.
2. Use the different logging levels available to you error/warning/info/debug/trace.
3. Don't be afraid of putting into too many logs.

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
2. Set the span name to the functions module name + the functions qualified name
   automatically
3. Catch errors and mark the span as failed and register the exception against the span
   so it gets sent to the collector.

### Tracing every method in a class

Instead of having to annotate every method in a class with `@baserow_trace` you can
use the `baserow_trace_methods` function which generates a metaclass that does it for
you. By default, it will trace all methods in the class not starting with `_`.

`baserow_trace_methods` also supports the `only` and `exclude` parameters which
let you restrict which exact methods to trace.

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)


class SomeClass(metaclass=baserow_trace_methods(tracer)):
    def a(self):
        pass

    def b(self):
        pass

    def c(self):
        pass

    def d(self):
        pass
```

This comes in very useful when working with a class that has abstract methods that
will be implemented by many sub classes (which we do allot in Baserow).

See below for an example of how to trace every single subclasses implementation of
`.do` for an abstract base class!

```python
import abc
from opentelemetry import trace

tracer = trace.get_tracer(__name__)


class ActionType(metaclass=baserow_trace_methods(tracer, abc=True, only='do')):
    @abc.abstractmethod
    def do(self):
        # Every sub class of ActionType will have their `do` method traced!
        pass

    def b(self):
        pass

    def c(self):
        pass

    def d(self):
        pass
```

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
the [OTEL Python API](https://opentelemetry.io/docs/instrumentation/python/manual/#tracing).
The helper functions
shown above are just to help you.

## How to track metrics

You can also keep track of various numerical and statistical metrics using open
telemetry. We don't provide any helper methods as the otel functions are
straight-forward.
Read [this](https://opentelemetry.io/docs/instrumentation/python/manual/#creating-and-using-synchronous-instruments)
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

## traceidratio and force full trace

If you've set a tracer sampler using the `traceidratio`, then not every request will
have a full trace.

```
OTEL_TRACES_SAMPLER_ARG: "0.1"
OTEL_TRACES_SAMPLER: "traceidratio"
```

It can hold you back if you want to debug a specific request. We've therefore
implemented a query parameter that allows you to force a full trace. You can add
`?force_full_otel_trace=true` to any backend request to get a full trace back.
