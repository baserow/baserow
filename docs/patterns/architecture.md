# Architectural patterns

This page describes the layered shape that the backend and frontend both follow.
Almost every feature in Baserow is built out of these same pieces — once you can
trace a request through them end to end, you can read most of the codebase.

For the inventory of which subsystems exist, see
[Systems overview](../technical/systems-overview.md). For how those subsystems make
themselves pluggable, see [Registries](registries.md).

## Backend layers

```
                 ┌──────────┐
HTTP request ──▶ │  View    │  api / urls / serializers — deserialise, validate,
                 └────┬─────┘  call the right service or action, return response.
                      │
                 ┌────▼─────┐
                 │ Service  │  Optional. Permission checks, efficient fetch, glue
                 └────┬─────┘  between view and (action OR handler).
                      │
                 ┌────▼─────┐
                 │  Action  │  Optional. Records an Action row for audit + undo/redo.
                 └────┬─────┘  Wraps a handler call; not every operation is an action.
                      │
                 ┌────▼─────┐
                 │ Handler  │  Business logic across multiple models. Emits signals.
                 └────┬─────┘
                      │
                 ┌────▼─────┐
                 │   ORM    │  Django models.
                 └────┬─────┘
                      │
                 ┌────▼─────┐
                 │    DB    │  PostgreSQL.
                 └──────────┘

                 Handler ──signals──▶ Receivers ──websocket──▶ frontend
                 Handler ──long-task──▶ Celery worker
```

### View

Lives under `backend/src/baserow/.../api/`. Responsibilities:

- Deserialise the request with a DRF serializer.
- Map domain exceptions to HTTP responses (`map_exceptions`).
- Delegate to a service or, if there is no service, directly to an action or handler.
- Serialise the result for the response.

Views must not contain business logic. The rule of thumb: a view should read like a
sentence. If you can't summarise it in one, push the work down.

### Service

A relatively newer layer; the rollout is incremental, so coverage is uneven. New
code should default to a service; direct view→handler is fine for trivial reads
but is considered legacy for anything more involved.

Create a service when the operation needs any of:

- **Permission checks** via `CoreHandler.check_permissions()`.
- **Optimised fetching** — loading just enough data for this operation rather than
  pulling in everything a generic handler method would.
- **Composing multiple handler calls** when the view-level operation crosses
  domains.

Services live next to handlers in the domain folder, typically as `service.py`.
Examples to copy from: `baserow.core.service`,
`baserow.core.notifications.service`, `baserow.contrib.database.table.service`,
`baserow.contrib.database.views.service`,
`baserow.contrib.automation.nodes.service`. (Note that
`baserow.core.services` is a separate concept — it's the dispatch system for
the builder application's data sources, not the architectural service layer
discussed here.)

Rule of thumb: if you're tempted to put permission-checking logic directly in a
view, you want a service instead.

### Action

An `ActionType` describes a state change worth recording. It writes a row to the
`Action` table (audit log) and, if undoable, exposes `undo()` / `redo()` methods.
Not every operation is an action — GET requests, idempotent queries, and pure read
flows skip straight to a handler.

The terminology to keep straight:

- **`ActionType`** — the *kind* of action, registered in `action_type_registry`. It
  defines `do()`, `undo()`, `redo()` and the params it accepts.
- **`Action`** — a Django model row recording that one specific occurrence of an
  `ActionType` happened, with its params, scope, user, and timestamp. This is what
  populates the audit log.
- **`ActionHandler`** — the orchestrator. It's what views/services call. It looks up
  the `ActionType`, runs `do()` inside a transaction, writes the `Action` row,
  emits the `action_done` signal, and handles undo/redo lookup.

A typical `ActionType.do()` does three things: validate inputs, call into a handler
to do the work, and return a structure rich enough to undo. See
`baserow/contrib/database/rows/actions.py` for representative examples and
[Undo/redo guide](../technical/undo-redo-guide.md) for the model.

### Handler

A handler is a class encapsulating business logic that spans multiple models — the
seam between the ORM and the action/service layer. Examples: `TableHandler`,
`FieldHandler`, `RowHandler`, `ViewHandler`, `CoreHandler`. Handlers are where the
real work happens: cross-model queries, transactional writes, emitting signals,
scheduling Celery tasks.

A handler method should be callable from a shell, a management command, or a test
without going through HTTP. If you can't, the layering is wrong.

### Signals

After a handler mutates state it emits Django signals (e.g. `rows_created`,
`field_updated`, `table_created`). Receivers in `baserow.ws.*`, `baserow.core.search`,
`baserow.core.notifications`, and the formula/field-dependency code react to those
signals. Signals are how a single write fans out to "send websocket update",
"reindex search", "recompute dependent formulas", "send notification", without each
handler having to know about all of those concerns.

Concrete example — what happens after `RowHandler.create_row()`:

1. The row is inserted via the dynamic model's ORM.
2. The handler emits `rows_created`.
3. A receiver in `baserow.ws.*` translates that into a websocket message addressed to
   subscribers of the table's page.
4. The search code reindexes the affected TSV columns.
5. The formula/field-dependency code recomputes any fields that depend on the new
   row.
6. The notification code may emit a "row mention" notification if a mention was added.

### Celery

Long-running work moves to Celery: large imports, exports, snapshots, duplications,
search reindex backfills, periodic trash cleanup. The
[Job system](../technical/systems-overview.md#job-system) is the user-facing wrapper
around this: a `JobType` represents one kind of long operation with progress,
cancellation and realtime updates. Internal periodic tasks (cron-style) are
registered with the Celery beat scheduler.

A handler that needs background work either schedules a Celery task directly (for
internal housekeeping) or creates a Job (for user-visible long operations).

## Frontend layers

```
            ┌────────────┐
User UI ──▶ │ Components │  Presentation, Vue templates and behaviour.
            └─────┬──────┘
                  │ dispatch
            ┌─────▼──────┐
            │ Vuex Store │  Application state.
            └─────┬──────┘
                  │
            ┌─────▼──────┐
            │  Service   │  HTTP calls to the backend REST API (axios).
            └─────┬──────┘
                  │ XHR
                  ▼
                Backend

            Backend ──websocket──▶ Realtime handlers ──▶ Store
            Backend ──websocket──▶ Notification handlers ──▶ Notification store
```

### Components

Vue components own presentation and local UI behaviour only. They dispatch actions
to the store; they should not call services directly.

### Vuex store

Contains application state. Components subscribe to it; actions and mutations update
it. The store is also the destination for realtime updates pushed from the backend.

### Service

The frontend "service" is just the typed wrapper around `axios` that hits the REST
API. It returns plain data; it does not own state. Store actions call services.

### Realtime handlers

For each websocket message type the backend emits, the frontend has a handler that
applies the change to the store. The pattern is symmetrical with the backend: the
backend signals → ws receivers → message; the frontend receives the message →
realtime handler → store update → reactive re-render.

### Notification handlers

Notification messages are a special kind of websocket message that also land in the
notification store, drive the unread counter, and surface in the notification panel.

## Reading a feature end to end

Picking any feature and tracing it through these layers — view → service → action →
handler → signal → ws receiver → frontend handler → store → component — is the
single most useful exercise for ramping up. Pick a small one (`row update` is a
good first walk-through; `field create` is the next step up; `field type
conversion` is the level after that).
