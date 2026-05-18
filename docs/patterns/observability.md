# Observability — logging, tracing, verifying in prod

Three things this page covers:

1. **Logging** — what to log, what not to log, conventions.
2. **OpenTelemetry tracing** — how Baserow instruments code, and how to add
   instrumentation that matters.
3. **Verifying assumptions in production** — how to answer "is what I think
   is happening actually happening?" using the data we already collect.

Production traces land in Honeycomb. See also
[Metrics and logs](../development/metrics-and-logs.md) and
[Monitoring Baserow](../installation/monitoring.md).

## Logging

We use [loguru](https://github.com/Delgan/loguru). Import the logger directly
from any module:

```python
from loguru import logger

logger.info("imported {count} rows", count=len(rows))
logger.warning("unexpected state: {state}", state=state)
logger.exception("import failed for table {table_id}", table_id=table.id)
```

Conventions:

- **Use keyword placeholders, not f-strings.** Loguru extracts the kwargs as
  structured fields, which makes the logs queryable. f-strings flatten
  everything into a single rendered message and lose the structure.
- **`logger.exception(...)` from inside `except:`.** It captures the
  traceback. Don't `logger.error(str(exc))` — you lose the stack.
- **Levels.** `debug` for verbose internals, `info` for noteworthy normal
  state, `warning` for unexpected-but-not-broken, `error` for handled but
  serious, `exception` for unhandled-in-this-frame errors.
- **Default backend log level is `INFO`** (`BASEROW_BACKEND_LOG_LEVEL`).
  Don't ship `info` logs that fire many times per request.

### What to log

- **Boundaries that produce side effects:** outbound webhooks, email sends,
  external API calls, Celery task starts and finishes.
- **Branch points an operator would need to debug an incident:** "fell back
  to lenient schema conversion for field X", "search index rebuild started
  for workspace Y".
- **Unhandled or recovered errors** with the relevant ids and context.
- **Long-running steps** with timing — log the start *and* the finish so you
  can compute durations from log timestamps.

### What not to log

- **PII.** Email addresses, names, row values, formula content. If you have
  to log them, log the id and let the operator look it up.
- **Per-row chatter in loops.** Move the log outside the loop and aggregate.
- **Secrets, tokens, credentials.** Ever.
- **Things you can already see in OTEL traces.** Span attributes are
  queryable; don't double-log.

## OpenTelemetry tracing

OTEL is the primary way we understand production behaviour. A trace per
request, with spans for handler methods, Celery tasks, outbound HTTP, DB
queries, and explicit user code.

### Auto-tracing handler classes

Most handler classes are auto-traced via the `baserow_trace_methods`
metaclass:

```python
from opentelemetry import trace
from baserow.core.telemetry.utils import baserow_trace_methods

tracer = trace.get_tracer(__name__)

class RowHandler(metaclass=baserow_trace_methods(tracer)):
    def create_row(self, user, table, values):
        ...
```

Every method on the class automatically becomes a span. Optionally restrict
to specific methods (`only=["do", "undo", "redo"]`) — the `ActionType` base
class uses this to trace only the public methods.

### Tracing one function

For a single function (Celery task, helper) use the decorator:

```python
from baserow.core.telemetry.utils import baserow_trace

@baserow_trace(tracer)
def update_search_data(table_id):
    ...
```

### Adding attributes

Spans become useful when they carry context. Add attributes to the current
span via `add_baserow_trace_attrs(...)`:

```python
from baserow.core.telemetry.utils import add_baserow_trace_attrs

add_baserow_trace_attrs(table_id=table.id, row_count=len(rows))
```

Attributes are namespaced under the `baserow.` prefix automatically. Add only
fields you expect to query, such as strategy names, table ids, workspace ids,
or row counts.

### User context in spans

`setup_user_in_baggage_and_spans(user, request)` (in
`baserow.core.telemetry.utils`) attaches the user id and session id to the
current span *and* propagates them as OTEL baggage so downstream spans (e.g.
inside a Celery task spawned from this request) inherit the same fields.
The `BaserowOTELMiddleware` wires this up for HTTP requests; you only need
to call it directly in Celery tasks that need user context.

### What to instrument

- **Anything that crosses a layer boundary** worth tracking duration on
  (view → service → handler → ORM).
- **Anything where the time spent answers "where did the request go?"** A
  span around a single line that does work is almost always useless; a span
  around a method that calls into other handlers is almost always useful.
- **Things you'd want to alert on** — slow handler calls, search index
  rebuilds, formula recomputes.

### What NOT to instrument

- **Trivial pure functions.** Span overhead exceeds the work.
- **Tight loops.** One span per iteration overwhelms the trace.
- **Code already covered by the metaclass.** Don't double-wrap.

### Suppressing instrumentation

If a function shouldn't generate spans (e.g. periodic health checks that
would dwarf real traffic), wrap it in `@disable_instrumentation`:

```python
from baserow.core.telemetry.utils import disable_instrumentation

@disable_instrumentation
def health_check_loop():
    ...
```

## Verifying assumptions in production

The point of all the above is that you can answer questions like "is my
change actually doing what I think it is?" without redeploying with extra
logging.

### Pattern 1 — "How often is this code path hit?"

Find the span in Honeycomb. Count by attribute. If your branch instruments
its choice as a span attribute (`add_baserow_trace_attrs(branch="fast")`),
you can group and compare.

If the code path isn't traced, add a span attribute on the relevant handler
method *before* deploying the change you want to measure. Then in the next
release you can compare.

### Pattern 2 — "How long does this thing take?"

Honeycomb gives you duration percentiles on any span name. If a method
matters enough to keep an eye on, put it on a handler class (covered by the
metaclass) or wrap it in `@baserow_trace`.

### Pattern 3 — "Did this user actually do X?"

`setup_user_in_baggage_and_spans` puts `user.id` on the span and propagates
it via baggage. You can filter by `user.id == ?` in Honeycomb and see every
trace the user touched, across HTTP and Celery boundaries.

For finer state — "what params did they pass" — use span attributes, not
logs. Logs are best for narrative; spans are best for aggregation.

### Pattern 4 — "What happens after my change deploys?"

Before deploying:

1. Add one or two span attributes that distinguish the new path from the
   old (e.g. `add_baserow_trace_attrs(strategy="v2")`).
2. Identify the metric that should move (latency, count, error rate).
3. Pick the Honeycomb query in advance.

After deploying, run the query. The strongest "I verified this in prod" you
can give in a PR review is a Honeycomb link.

### Pattern 5 — "Was it really an N+1?"

Honeycomb shows the number of DB spans inside each parent span. If the
count grows with the page size of the affected listing, it's N+1. Add a
query-count test (see [queries](queries.md#cheat-sheet-writing-a-new-handler-method))
to lock in the fix.

## Configuration knobs

Relevant environment variables:

- `BASEROW_BACKEND_LOG_LEVEL` — overall backend log level. Default `INFO`.
- `BASEROW_BACKEND_DATABASE_LOG_LEVEL` — Django DB queries. Default `ERROR`
  (set to `DEBUG` locally to see every query).
- `BASEROW_DJANGO_REQUEST_LOG_LEVEL` — request log level. Default `ERROR`.
- OTEL exporter settings — see
  [Monitoring Baserow](../installation/monitoring.md).

## Gotchas

- **f-string vs keyword logging.** `logger.info(f"id={x}")` works but loses
  the structured field. `logger.info("id={id}", id=x)` keeps it queryable.
  Use the second form.
- **Double-tracing.** Handler classes are already traced via the metaclass.
  Adding `@baserow_trace` on individual methods is redundant and clutters
  traces.
- **PII in span attributes.** Same rule as logs: ids only, no values.
- **`logger.exception` outside `except`.** Use `logger.error` if you don't
  have a live exception — `.exception()` will log "NoneType: None" if there's
  no traceback available.
- **Span attributes are sampled.** High-cardinality attributes (one unique
  value per request) survive; the volume of traffic decides what makes it to
  Honeycomb. Don't put debugging data behind a "set a low-frequency
  attribute" trick — sampling will swallow it.

## Related

- [Metrics and logs](../development/metrics-and-logs.md).
- [Monitoring Baserow](../installation/monitoring.md).
- [Queries](queries.md) — for the N+1 query-count test pattern.
- `baserow.core.telemetry.utils` — the source of the helpers used here.
