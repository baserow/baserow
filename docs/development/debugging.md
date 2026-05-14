# Debugging

The practical "something's wrong, where do I look" reference. Organised by
what you're trying to do, not by tool.

Sections:

- [Pick your tracing backend](#pick-your-tracing-backend)
- [Backend debugging tools](#backend-debugging-tools)
- [Frontend debugging tools](#frontend-debugging-tools)
- [VSCode setup](#vscode-setup) — separate so users on other IDEs can skip it
- [Baserow-specific debugging recipes](#baserow-specific-debugging-recipes)
- [Gotchas](#gotchas)

## Pick your tracing backend

Baserow emits OpenTelemetry spans out of the box (see
[observability](../patterns/observability.md)). To make those useful locally
you need somewhere to send them. Three reasonable choices:

### Sentry (hosted, free tier) — recommended default

[sentry.io](https://sentry.io) gives you error tracking and OTEL traces in
one product. Set up a personal project, copy the DSN into `.env.local` as
`SENTRY_DSN`, and you'll see exceptions and traces from your local dev
backend within seconds. Same flow for frontend (separate Sentry project,
separate DSN). The free tier comfortably covers a personal dev rig.

When you suspect a real bug, this is the highest-leverage tool because
each exception comes pre-populated with the trace that led to it.

### Jaeger via docker-compose — fully local, no signup

Add a `jaeger` service alongside the existing dev stack and point the OTEL
exporter at it. Jaeger Tracing on Docker Hub gives you the all-in-one
image in one container:

```yaml
# add to docker-compose.dev.yml (or a separate override file)
jaeger:
  image: jaegertracing/all-in-one:latest
  ports:
    - "16686:16686"  # UI
    - "4317:4317"    # OTLP gRPC
    - "4318:4318"    # OTLP HTTP
```

Then set `BASEROW_ENABLE_OTEL=true` and the standard
`OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318` env var. The UI lives
at http://localhost:16686.

Trade-off vs Sentry: pure tracing, no error tracking, no automatic source
links — but no data leaves your machine.

### Honeycomb — for production

baserow.io traces land in Honeycomb. Use it when you need to debug
something you can only see in production. Don't point dev at it; the
signal-to-noise ratio is awful.

## Backend debugging tools

### `just b shell_plus --print-sql`

The single most useful command for "what query does my code actually
emit?". `shell_plus` (from `django-extensions`) launches an interactive
Python shell with every Baserow model auto-imported. `--print-sql` echoes
every SQL statement that runs, with timing.

```bash
just b shell_plus --print-sql
```

Inside the shell, you can run arbitrary code and see the queries it
produces:

```python
table = Table.objects.get(pk=42)
model = table.get_model()  # see every query the cache misses
list(model.objects.all())   # the actual SELECT
```

Use this any time you suspect a handler is doing more work than it
should. Pair with [queries.md](../patterns/queries.md) for the patterns
that fix what you find.

### `django-silk` — live request profiler

Browse to http://localhost:8000/silk/ after starting Baserow in dev. Every
request the backend handles is logged with its full query list, timings,
and a flame-graph view. Indispensable for spotting N+1s in real flows.

Some useful queries to try:

- Sort by "Number of queries" → find N+1 candidates.
- Sort by "Time spent on queries" → find slow queries.
- Click a request → see which view ran it and the per-query timing.

`BASEROW_ENABLE_SILK` controls whether silk is wired up; default is on in
dev. Turn it off if it's interfering with a performance measurement —
silk's own overhead is non-trivial.

### `django-admin show_urls`

Lists every URL registered in the project. Use it when you can't find
which view handles a particular endpoint:

```bash
just b show_urls | grep -i 'group_by'
```

### Flower — Celery monitor

http://localhost:5555/. Real-time view of Celery workers and tasks. Use
it when:

- You scheduled a job and it never ran (check the worker is alive).
- A job is failing and you can't find the error (Flower shows tracebacks).
- A task is being retried too aggressively (check the retry count).

### `breakpoint()` / `ipdb`

Standard `breakpoint()` works. In the dev container, attach to the
backend container first (`docker attach <container>`) so stdin reaches
the debugger.

If you'd rather skip the attach dance, use a VSCode launch config (see
below) — that gives you breakpoints from the editor.

### Loguru and `BASEROW_BACKEND_DATABASE_LOG_LEVEL`

Set `BASEROW_BACKEND_DATABASE_LOG_LEVEL=DEBUG` to log every SQL query that
runs, not just inside `shell_plus`. Useful for short snippets you can run
end-to-end and grep through. For longer flows, prefer silk — the volume
of debug logs becomes unwieldy fast.

`BASEROW_BACKEND_LOG_LEVEL=DEBUG` does the same for application logs.
See [observability](../patterns/observability.md) for the logging
conventions.

## Frontend debugging tools

### Browser DevTools — primary tool

Open in Chrome / Firefox / Edge:

- **Console** — `console.log` output, errors, warnings.
- **Network** — every XHR / fetch / websocket message. Right-click → "Copy
  as cURL" to replay a failing request from the terminal.
- **Sources / Debugger** — set breakpoints in `.vue` and `.js` files
  served from the dev server. Use `debugger;` statements as another way
  in.
- **Application → Local Storage / IndexedDB** — inspect cached auth
  tokens and locally persisted state.

### Vue DevTools

Install the browser extension:
[Vue.js devtools](https://devtools.vuejs.org/). Gives you:

- A **components tree** with live props and data — click a component, see
  its current state.
- A **Vuex inspector** with **time-travel** — every mutation is logged;
  you can roll the store back to a previous state to bisect "when did
  this break". Worth its weight in gold for store-driven bugs.
- An **events** tab — every emitted event with payload.

Use it for any "the UI looks wrong" or "this Vuex action did the wrong
thing" bug.

### Vuex / store

Add temporary `console.log` statements at the top of an action or
mutation; or use the Vue DevTools mutation log instead — it's already
there for free.

If a realtime update from the backend isn't reflected in the UI, the
chain is:

1. Did the backend send the ws message? → check silk / OTEL.
2. Did the frontend receive it? → DevTools → Network → WS frames.
3. Did the registered realtime handler run? → add a log at the entry
   point or set a Vue DevTools breakpoint.
4. Did the handler dispatch the right mutation? → Vuex log.

### Network / API debugging

For poking at the API directly:

- **Browser → Network tab** is fastest for replaying what the frontend
  already did.
- **`httpie`** (`brew install httpie`) gives you cleaner curl ergonomics
  for ad-hoc requests.
- **Bruno**, **Insomnia**, or **Postman** for saved request collections.
- **VSCode REST Client** extension if you live in the editor — `.http`
  files with one request per block, response inline.

### Mail catcher

In dev, outbound emails are sent to a local mail catcher
(`mailhog` / `mailpit`-style service in `docker-compose.dev.yml`). Browse
its UI to read what would have been sent. Useful for testing
notification flows and password reset emails without spamming a real
inbox.

## VSCode setup

(Skip if you use another IDE — none of this is required to develop
Baserow. The other tools above work the same regardless.)

VSCode has good Python and JavaScript / Vue support out of the box. Two
things worth setting up: launch configurations for breakpoint debugging,
and the right extensions.

### Recommended extensions

- **Python** (Microsoft) + **Pylance** — IntelliSense, type checking.
- **debugpy** — Python debugger (bundled with the Python extension).
- **Ruff** — fast Python linter, matches the project's formatting.
- **Vue (Official)** (Volar) — Vue 3 IntelliSense and template
  type-checking. Disable Vetur if you have it; the two conflict.
- **ESLint** — JavaScript / Vue linting.
- **EditorConfig** — respects the repo's `.editorconfig`.

The Baserow repo has a `.vscode/` directory with `launch.json`,
`tasks.json`, and `settings.json` covering the common entry points
(backend runserver, frontend dev server, celery worker, pytest, jest).
You can copy / adapt the configurations to your local environment.

### Launch configurations

`.vscode/launch.json` defines named debug profiles. Common ones the repo
provides (configuration names paraphrased — see your local
`launch.json`):

- **Backend: runserver** — `debugpy` launching `backend/baserow runserver
  0.0.0.0:8000`. Attach breakpoints in any backend `.py` file; the
  request will pause when it hits them.
- **Celery: worker (pool=solo)** — `debugpy` launching `celery -A
  baserow worker --pool=solo` so the worker runs in-process and your
  breakpoints fire.
- **pytest: current file** — `debugpy` launching `pytest ${file} -v -s`
  for running and debugging the test file you're currently viewing.
- **Frontend: dev** — Node launch for `yarn run dev`. Pair with a
  Chrome / Edge launch (see below) to set breakpoints in `.vue` and `.js`
  files.
- **Jest: current file** — Node launch for `node_modules/jest/bin/jest`
  on the current file.

### Secrets in launch.json — please don't

`launch.json` is committed to the repo. Do not put real API keys,
license tokens, or DSNs in it. Two safer patterns:

1. **Reference an `.env.local` file** via the `envFile` field:

   ```jsonc
   {
     "name": "Backend: runserver",
     "type": "debugpy",
     "envFile": "${workspaceFolder}/.env.local",
     "env": {
       "DJANGO_SETTINGS_MODULE": "baserow.config.settings.dev"
     }
   }
   ```

   Put secrets in `.env.local` and add it to `.gitignore`. Already
   ignored at the repo root.

2. **Read from your shell environment** via `${env:VARNAME}`:

   ```jsonc
   "env": {
     "OPENAI_API_KEY": "${env:OPENAI_API_KEY}"
   }
   ```

   Set the variables in your shell rc (`~/.zshrc`, etc.) — never in
   committed config.

If you've already committed secrets, **rotate them**. `git filter-repo`
or BFG can rewrite history, but treat any leaked key as compromised.

### Debugging Vue in VSCode

To set breakpoints in `.vue` and `.js` files from inside VSCode:

1. Start the frontend dev server (`yarn run dev` or your Frontend launch
   config). It serves on http://localhost:3000.
2. Add a Chrome / Edge launch config:

   ```jsonc
   {
     "name": "Frontend: attach to Chrome",
     "type": "chrome",  // or "msedge"
     "request": "launch",
     "url": "http://localhost:3000",
     "webRoot": "${workspaceFolder}/web-frontend"
   }
   ```

3. Launch it. VSCode opens a Chrome window connected to its debugger.
   Set breakpoints in `.vue` files — they'll fire when the page runs the
   relevant code.

Most people end up using **Chrome / Edge DevTools directly** instead of
the VSCode debugger for frontend work — the DevTools network and Vuex
panels are too useful to give up. Pick what you prefer; both work.

## Baserow-specific debugging recipes

### "Why is this field acting weird?"

Field-behaviour mysteries trace to one of three things: the `FieldType`,
the dynamic model cache, or the field-dependency graph.

```python
# In shell_plus
table = Table.objects.get(pk=...)
model = table.get_model()
model.info()  # rich-printed table of every field

field = Field.objects.get(pk=...).specific
field_type = field_type_registry.get_by_model(field)
print(type(field), type(field_type))

# Force a cache miss
from baserow.contrib.database.table.cache import invalidate_table_in_model_cache
invalidate_table_in_model_cache(table.id)
model = table.get_model()
```

If the field's value looks right in the DB but wrong via the model, the
generated model is likely stale. `Table.version` should bump on every
field change.

### "Why didn't I get a realtime update?"

Walk the chain:

1. Did the **handler emit the signal**? `breakpoint()` after the
   mutation, confirm the right signal is sent.
2. Did a **ws receiver fire**? Check `baserow.ws.*`; add a log statement
   at entry, or set `BASEROW_BACKEND_LOG_LEVEL=DEBUG`.
3. Did the **message reach the right page**? `page_registry` decides
   subscribers. Mismatched page id = no broadcast.
4. Did the **frontend handler run**? Browser → Network → WS frames; then
   Vue DevTools to see the Vuex mutations.

See [websockets guide](../technical/websockets.md).

### "Why is this query slow?"

1. Hit the endpoint with silk on.
2. If query count grows with page size → N+1. Fix per
   [queries.md](../patterns/queries.md).
3. If count is small but one query is slow → missing index or unbounded
   queryset. `EXPLAIN ANALYZE` via `shell_plus`:

   ```python
   from django.db import connection
   with connection.cursor() as c:
       c.execute("EXPLAIN ANALYZE SELECT ...")
       for row in c.fetchall():
           print(row[0])
   ```

4. If it's a search query → check the TSV column is built and
   `SearchHandler` isn't lagging.

### "Why did my migration fail in CI but pass locally?"

- Local DB is smaller; you skipped batching that prod-scale needs.
- Local DB is missing a constraint that prod has.
- You forgot `atomic = False` on a `CREATE INDEX CONCURRENTLY` migration.
- You imported a model directly instead of using `apps.get_model()`.

See migration conventions in
[creating features](../patterns/creating-features.md).

### "Why is undo not undoing this thing?"

Check whether the operation goes through an `ActionType`. If it doesn't,
nothing to undo. If it does:

1. Right `scope()`? Undo is scope-filtered.
2. `Params` round-trips through JSON cleanly?
3. Exceptions in undo? They're logged but the action row is marked
   undone-with-error.

See [action system](../technical/action-system.md).

### "Why is the test passing but production failing?"

- **Cache differences.** Tests use in-memory cache; prod uses Redis. An
  invalidation race that always wins in memory may lose in prod.
- **Transaction isolation.** Tests roll back each test. `on_commit`
  callbacks don't fire unless you opt in with
  `TestCase.captureOnCommitCallbacks(execute=True)`.
- **Search index not built.** Tests skip async search reindex.
- **Different ordering.** Production interleaves; tests serialise. Race
  conditions hide.

### "I want to reproduce a production bug locally"

- **Snapshot import.** If you have access to a snapshot of the user's
  data, install it into a local workspace via the snapshots feature.
  Bug usually reproduces with a fraction of the data.
- **Templates.** If the bug is data-shape-dependent, a template captures
  the schema without the volume.
- **`fill_table_rows` management command.** Generate large synthetic
  tables to reproduce performance bugs.
- **`run_periodic_fields_updates` management command.** Manually trigger
  periodic recalcs for a specific workspace.

### "Bisecting a regression"

`git bisect` works as advertised; `just b show_urls` or a one-line
shell_plus check can serve as the test condition. Use it when "this
worked last week but doesn't now" and there are dozens of merged PRs to
sift through.

## Gotchas

- **`Table.get_model()` returns a fresh class each time.** Don't
  `is`-compare generated model classes. See
  [dynamic models](../technical/dynamic-models.md).
- **Lenient field-type conversion silently nulls unconvertible values.**
  If data disappeared after a type change with no error, this is why.
  See [field system](../patterns/field-system.md).
- **`on_commit` doesn't fire inside `TestCase`** unless you opt in.
- **Signals can fail silently.** A raise in one receiver doesn't stop
  the others, but it also doesn't surface to the caller. Log exceptions
  in receivers.
- **Soft-deleted (trashed) rows are filtered by the default manager.**
  Use `Model.trash` to see them.
- **The local cache is per-request.** Anything cached via `local_cache`
  is lost after the request. Don't use it for cross-request state.
- **Cachalot must be opt-in for user tables.** A query that "should be
  cached" but isn't is probably outside `cachalot_enabled()`.
  See [caching](../technical/caching.md).
- **Action signals fire on undo/redo too.** Filter by
  `action_command_type` if you don't want all three.
- **silk has overhead.** Disable when measuring real performance.
- **Vue DevTools time-travel mutates the store live.** If you replay to
  an old state and then continue using the app, you'll see weird
  behaviour because the backend doesn't know you rewound. Reload after
  time-travel debugging.

## Related

- [Observability](../patterns/observability.md) — logging and OTEL.
- [Queries](../patterns/queries.md) — N+1 and ORM tips.
- [Architectural patterns](../patterns/architecture.md) — where to
  suspect the bug is.
- [Running tests](running-tests.md),
  [running the dev env locally](running-the-dev-env-locally.md).
