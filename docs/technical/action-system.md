# Action system

The action system is the event-based backbone of state changes in Baserow. Any user
operation that mutates state — creating a row, renaming a table, deleting a view,
importing data — goes through it. The system gives you three things essentially for
free once an operation is modelled as an action:

1. An audit row in the `Action` table, so we know who did what and when.
2. Undo/redo support, for operations that opt into it.
3. A consistent signal (`action_done`) that other subsystems can listen to.

If you've read [the architectural patterns](../patterns/architecture.md), this is
the layer between **service** and **handler** in the backend flow.

## The three types you keep straight

| Concept | Lives in | What it is |
|---|---|---|
| **`ActionType`** | `baserow.core.action.registries` (and per-domain `actions.py` files) | The *kind* of action. Defines `do()`, parameters, scope, and (if undoable) `undo()`/`redo()`. Registered in `action_type_registry`. |
| **`Action`** | `baserow.core.action.models` | A Django model row: one specific occurrence of an `ActionType` happening, with its params, scope, user, session, timestamps. This populates the audit log. |
| **`ActionHandler`** | `baserow.core.action.handler` | The orchestrator. Drives `undo()` and `redo()` for a user across the latest action(s) within a set of scopes. |

A common confusion early on: views and services usually call the class method
`SomeActionType.do(...)`, not `ActionHandler`. Inside `do()`, the implementation
calls `cls.register_action()` to record the `Action` row, then delegates to a
handler for the actual mutation. `ActionHandler` is for undo/redo orchestration.

Read `backend/src/baserow/contrib/database/rows/actions.py` for canonical examples.

## Shape of an `ActionType`

A representative `ActionType` defines:

- A `type: str` identifier (registered in `action_type_registry`).
- A nested `Params` dataclass holding everything needed to undo or redo the change
  later. Stored as JSON in the `Action.params` column.
- `do(cls, ...)` — performs the operation, calls `register_action(...)` to record
  it, returns the result (often the created/updated object). The arguments are
  domain-specific (typically `user`, the relevant resources, and the change being
  made).
- `scope(cls, ...)` — returns an `ActionScopeStr` (e.g. for table 42, "table42").
  Scopes control which actions the user sees when they hit undo — undo is
  scoped, not global.
- Optional: `params_to_serializable()` / `serialized_to_params()` hooks if the
  `Params` dataclass needs special handling round-tripping through JSON.

Undoable types also implement:

- `undo(cls, user, params, action_being_undone)` — reverses the change.
- `redo(cls, user, params, action_being_redone)` — re-applies the change.

The base classes are in `baserow.core.action.registries`:

- `ActionType` — non-undoable.
- `UndoableActionType` — undoable. Inherits the `UndoableActionTypeMixin`.

## Scopes

Every action is recorded with a scope. Scopes are how undo/redo is partitioned:
when a user presses undo, the frontend tells the backend which scopes the user is
currently "in" (the table they're looking at, the workspace, etc.), and
`ActionHandler.undo()` only considers actions in those scopes.

Scopes are *per-domain*, not per-workspace. A scope string looks like
`table42` (table 42), `view100` (view 100), `application7`, `workspace3`,
etc. A user's undo stack while editing rows in table 42 is independent from
their undo stack in table 99, even though both tables live in the same
workspace.

Scope types are registered in `action_scope_registry` (see `ActionScopeType` in
`backend/src/baserow/core/action/registries.py`). Each scope type implements `value()` to
build an `ActionScopeStr` from runtime context.

## Undo and redo

`ActionHandler.undo()` and `ActionHandler.redo()` walk the latest action(s) for a
user, in the given scopes, in the given client session, and call the type's
`undo()` / `redo()`. A few non-obvious behaviours:

- **Per-session.** Undo stacks are per browser session (via the untrusted client
  session id), not global per user. Opening another tab gives you another stack.
- **Action groups.** Operations that semantically belong together (e.g. creating
  several fields in one go) write multiple `Action` rows that share an
  `action_group` UUID. Undo treats the whole group as one step; `redo` too.
  See `get_client_undo_redo_action_group_id`.
- **Atomic.** Group undo runs inside a `transaction.atomic()`. If one action in
  the group fails, all of them get their `error` recorded and `undone_at` set,
  and the user sees the failure on the next attempt.
- **Lock conflicts.** `select_for_update(of=("self",))` is used when picking the
  latest action; a `LockConflict` is raised if another undo/redo is already in
  flight for the same row.
- **`web_socket_id` clearing.** Before running undo/redo, the handler clears the
  user's `web_socket_id` so that the realtime events triggered by the undo are
  also broadcast back to the user who triggered the undo — they want to see the
  state change.

## When to make something an action

Yes:

- Any state-changing operation a user can do that we want in the audit log.
- Any state-changing operation where undo makes sense from the user's
  perspective.

No:

- GET / read endpoints.
- Internal housekeeping (periodic cleanup, background reindex, signal handlers).
- Operations triggered by another action (e.g. signal receivers that update
  search). The originating action covers them.

If you're unsure, make it an action. The cost is small and it records the change
in the audit log.

## Anatomy of a typical action implementation

A simplified shape (read the real ones in `backend/src/baserow/contrib/database/rows/actions.py`):

```python
from baserow.core.action.registries import UndoableActionType

class CreateRowActionType(UndoableActionType):
    type = "create_row"

    @dataclasses.dataclass
    class Params:
        table_id: int
        row_id: int
        row_values: dict

    @classmethod
    def do(cls, user, table, values):
        row = RowHandler().create_row(user, table, values)
        cls.register_action(
            user=user,
            params=cls.Params(table.id, row.id, values),
            scope=cls.scope(table.id),
            workspace=table.database.workspace,
        )
        return row

    @classmethod
    def scope(cls, table_id):
        return TableActionScopeType.value(table_id)

    @classmethod
    def undo(cls, user, params, action):
        RowHandler().delete_row_by_id(user, params.row_id, params.table_id)

    @classmethod
    def redo(cls, user, params, action):
        RowHandler().create_row(user, ..., params.row_values)
```

The real handlers do more: they return data rich enough to rebuild deleted state
on undo, they pass `send_realtime_update=False` to skip ws events for the actual
mutation (the action signal carries them instead), and they update `params` on
the action row if state shifts during undo.

## The `action_done` signal

When `do()`, `undo()`, or `redo()` finishes, `ActionType.send_action_done_signal()`
fires `action_done`. Receivers — primarily `baserow.ws.*` — translate it into
realtime websocket messages addressed at the right table/page subscribers. This
is how undo "shows up" in other tabs.

## Related

- [Undo/redo guide](undo-redo-guide.md) — the deeper undo-specific notes.
- [Architectural patterns](../patterns/architecture.md) — where actions fit in the
  request flow.
- [Systems overview](systems-overview.md#action-system).
