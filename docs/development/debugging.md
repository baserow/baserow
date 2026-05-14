# Debugging

A practical reference for the day-to-day "something's wrong, where do I
look" question. Three sections: **tools available**, **Baserow-specific
debugging recipes**, and **gotchas**.

## Tools available

### snoop — automatic Python tracing

[snoop](https://github.com/alexmojaki/snoop) traces a piece of code and
shows how variables change over time. Available globally — no import
needed.

```python
@snoop
def my_function():
    for i in range(5):
        a = i * 2

# Or as a context manager
with snoop:
    for row in rows:
        do_something(row)
```

Useful kwargs:

- `@snoop(depth=2)` — also traces functions called from the traced
  function (default depth is 1).
- `@snoop(watch_explode=['my_dict'])` — expands dicts/objects to show
  every key/attribute.

Pretty-print a variable manually with `pp(x)`. Most useful when you
already know roughly where the bug is and want a frame-by-frame view of a
short stretch of code.

### `django-extensions` — Django power tools

Available inside the backend container:

- `django-admin shell_plus` — interactive shell with Baserow models
  auto-imported. Faster than typing `from baserow... import` for ten
  minutes.
- `django-admin show_urls` — lists every registered URL. Use it when
  you can't find the view that handles a particular endpoint.
- `django-admin runserver_plus` — runserver with Werkzeug debugger
  attached.
- `django-admin graph_models` — generates a Graphviz ER diagram of the
  models in an app. Worth running once when learning a new area.

### `django-silk` — request and query profiler

Once Baserow is up in debug mode, browse to
http://localhost:8000/silk/. Every request is logged with its full query
list and timings. Indispensable for spotting N+1s in real flows —
particularly the dashboard views that fan out across the model graph.

### Flower — Celery monitor

http://localhost:5555/. Real-time view of Celery workers and tasks.
Use it when you suspect a job is failing silently, getting retried too
much, or stuck.

### `ipdb` / breakpoints

`breakpoint()` works as expected. In a container, attach with
`docker attach <container>` first, then `breakpoint()` drops you into
`ipdb`.

### OTEL traces in dev

If OTEL is configured in dev (see
[Monitoring Baserow](../installation/monitoring.md)), span data flows to
your local backend and is queryable. Most local devs skip this — the same
data is available locally via `django-silk`, and the loguru logs are
easier to grep.

## Baserow-specific debugging recipes

### "Why is this field acting weird?"

Most field-behaviour mysteries trace to one of three things: the
`FieldType`, the dynamic model cache, or the field-dependency graph.

```python
# In shell_plus
table = Table.objects.get(pk=...)
model = table.get_model()

# Inspect every field on the model
model.info()  # rich-printed table; dev-only

# Find the field type
field = Field.objects.get(pk=...).specific
field_type = field_type_registry.get_by_model(field)
print(type(field), type(field_type))

# Force a cache miss and rebuild
from baserow.contrib.database.table.cache import invalidate_table_in_model_cache
invalidate_table_in_model_cache(table.id)
model = table.get_model()
```

If the field's value looks right in the DB but wrong via the model, the
generated model is likely stale. Verify with `Table.version` — every
field change should bump it.

### "Why didn't I get a realtime update?"

Walk the chain:

1. Did the **handler emit the signal**? Add `breakpoint()` after the
   handler mutates state, check `dir(baserow.contrib.database.rows.signals)`
   for the expected signal, and confirm it's being sent.
2. Did a **ws receiver fire**? `baserow.ws.*` has receivers; add a log
   statement at the entry point or set `BASEROW_BACKEND_LOG_LEVEL=DEBUG`.
3. Did the **message reach the right page**? Each ws page has a
   `page_registry` entry that decides who subscribes. Mismatched page
   ids = no broadcast.
4. Did the **frontend handler run**? In the browser, the Vuex store
   action that processes the ws message logs in dev. Confirm the
   message type matches a registered realtime handler.

See [websockets guide](../technical/websockets.md) for the full path.

### "Why is this query slow?"

1. Hit the endpoint with `django-silk` on. Read the query list.
2. If query count grows with the page size → N+1. Find where the loop
   touches an FK or reverse-FK. Fix per [queries](../patterns/queries.md).
3. If query count is small but one query is slow → either a missing
   index (check `EXPLAIN ANALYZE` via raw SQL) or a poorly-bounded
   queryset (look for `.filter(...)` without an index-backed column).
4. If it's a search query → check the TSV column has been built;
   `SearchHandler` may be lagging.

### "Why did my migration fail in CI but pass locally?"

- Local DB is smaller; you may have skipped batching that prod-scale needs.
- Your local DB might be missing a constraint that prod has (e.g. a
  unique index added in a later migration).
- You forgot `atomic = False` on a `CREATE INDEX CONCURRENTLY` migration.
- You imported a model directly instead of using `apps.get_model()`.

See migration conventions in [creating features](../patterns/creating-features.md).

### "Why is undo not undoing this thing?"

Check whether the operation goes through an `ActionType`. If it doesn't —
i.e. the handler is called directly without an action wrapper — there's
nothing to undo. Add the action or use a different code path. See
[action system](../technical/action-system.md).

If the operation *is* an action but undo doesn't work:

1. Check the action ran with the right `scope()`. Undo is scope-filtered.
2. Check `Params` round-trips through JSON cleanly. A non-JSON-safe value
   in `Params` will cause silent breakage on undo.
3. Check there are no exceptions during undo — they're logged but the
   action row is still marked undone-with-error.

### "Why is the test passing but production failing?"

The most common culprit in Baserow tests:

- **Cache differences.** Tests use an in-memory cache; prod uses Redis.
  An invalidation race that always wins in memory may lose in prod.
- **Transaction isolation.** Tests typically run each test in a
  transaction that's rolled back. `on_commit` callbacks never fire by
  default. Wrap with `TestCase.captureOnCommitCallbacks(execute=True)` if
  you need them.
- **Search index not built.** Tests skip the async search reindex unless
  you flush Celery synchronously.
- **Different ordering.** Production traffic interleaves; tests run
  sequentially. Race conditions hide in tests.

### "I want to see every SQL query"

Set `BASEROW_BACKEND_DATABASE_LOG_LEVEL=DEBUG` (default is `ERROR` so DB
logs stay quiet). Each query appears in the loguru log with its timing.
Useful for short snippets; for full request analysis use `django-silk`.

### "I want to see what an OTEL trace would look like"

Add `add_baserow_trace_attrs(name="value", ...)` in the code path of
interest, then load the page locally and check the OTEL exporter output
(or run the Honeycomb URL if you have access). See
[observability](../patterns/observability.md).

## Gotchas

- **`Table.get_model()` returns a fresh class each time.** Don't `is`-compare
  generated model classes. See [dynamic models](../technical/dynamic-models.md).
- **Lenient field-type conversion silently nulls unconvertible values.**
  If data disappeared after a field type change with no error, this is why.
  See [field system](../patterns/field-system.md).
- **`on_commit` doesn't fire inside `TestCase`** unless you opt in.
- **Signals can fail silently.** A raise in one receiver doesn't stop
  the others, but it also doesn't surface to the caller. Always log
  exceptions in receivers.
- **Soft-deleted (trashed) rows are filtered by the default manager.**
  Use `Model.trash` (manager) to see them. They're not gone; they're
  hidden.
- **The local cache is per-request.** Anything you cache via `local_cache`
  is lost the moment the request ends. Don't use it for cross-request
  state; it'll look like the cache "doesn't work".
- **Cachalot must be opt-in for user tables.** A query that "should be
  cached" but isn't is probably outside the `cachalot_enabled()` context.
  See [caching](../technical/caching.md).
- **Action signals fire on undo/redo too.** If you have a receiver that
  reacts to `action_done`, it fires three times during a do/undo/redo
  sequence. Filter by `action_command_type`.

## Related

- [Observability](../patterns/observability.md) — logging and OTEL.
- [Queries](../patterns/queries.md) — N+1 and ORM tips.
- [Architectural patterns](../patterns/architecture.md) — where to suspect
  the bug is.
- [Running tests](running-tests.md), [running the dev env locally](running-the-dev-env-locally.md).
