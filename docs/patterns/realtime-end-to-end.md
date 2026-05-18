# Realtime end-to-end

Realtime keeps other clients in sync after one user changes state. This page
connects the backend signal path to the frontend store update path.

For the backend socket primitives see [WebSockets](../technical/websockets.md).
For frontend stores and `force<Verb>` actions see
[Frontend architecture](frontend-architecture.md).

## The Path

```
HTTP request
  -> View / Service / Action
  -> Handler mutates state
  -> Handler emits a Django signal
  -> ws receiver schedules broadcast with transaction.on_commit
  -> PageType broadcasts to a Channels group
  -> CoreConsumer sends JSON over websocket
  -> RealTimeHandler dispatches by message type
  -> frontend realtime handler dispatches force<Verb>
  -> Vuex mutation updates state
  -> components re-render
```

Example: row creation emits `rows_created`; the ws receiver broadcasts a
`rows_created` message to the table page group; the frontend database realtime
handler dispatches `view/forceCreate`.

## Critical Rules

- **Broadcast after commit.** Receivers wrap external side effects in
  `transaction.on_commit(...)`. If the transaction rolls back, no websocket
  message is sent.
- **Do not echo ordinary writes to the originator.** Pass the user's
  `web_socket_id` to the broadcast ignore parameter. The originator already has
  the HTTP response or optimistic state.
- **Undo/redo is different.** Undo/redo clears `web_socket_id` so the user who
  triggered the undo receives the realtime echo.
- **Realtime is additive, not the source of truth.** A client can miss a message
  before subscribing or while disconnected. Pages still fetch canonical state.
- **Frontend handlers use `force<Verb>`.** The backend has already persisted the
  change; the frontend should mirror it, not call the API again.
- **One concern per receiver.** Search, notifications, webhooks, audit log, and
  websocket broadcasting can all react to the same signal independently.

## Backend Pieces

| Piece | Role |
|---|---|
| Handler | Owns the state change and emits a past-tense signal. |
| Signal | Fanout point; emitter does not know who listens. |
| ws receiver | Serializes the message and schedules broadcast after commit. |
| `PageType` | Maps a page plus parameters to a Channels group. |
| Channels group | Delivers to subscribed websocket consumers. |
| `CoreConsumer` | Sends the JSON message to the browser. |

The row-create path is spread across:

- `backend/src/baserow/contrib/database/rows/handler.py`
- `backend/src/baserow/contrib/database/rows/signals.py`
- `backend/src/baserow/contrib/database/ws/rows/signals.py`
- `backend/src/baserow/contrib/database/ws/pages.py`
- `backend/src/baserow/ws/registries.py`
- `backend/src/baserow/ws/tasks.py`
- `backend/src/baserow/ws/consumers.py`

## Frontend Pieces

| Piece | Role |
|---|---|
| `RealTimeHandler` | Owns socket connection, subscriptions, and event dispatch. |
| Module `plugin/realtime.js` | Registers a module's realtime handlers. |
| Module `realtime.js` | Handles each message type. |
| Vuex `force<Verb>` action | Applies remote state without HTTP. |
| Mutation | Updates the same state shape used by local actions. |

Database examples live in:

- `web-frontend/modules/core/plugins/realTimeHandler.js`
- `web-frontend/modules/database/plugin/realtime.js`
- `web-frontend/modules/database/realtime.js`
- `web-frontend/modules/database/store/view/`

## Adding a Realtime Event

1. Emit or reuse a backend signal from the handler that owns the mutation.
2. Add a ws receiver in the relevant `contrib/.../ws/.../signals.py`.
3. Wrap the broadcast in `transaction.on_commit(...)`.
4. Pick the right `PageType` and pass `web_socket_id` for originator exclusion
   when appropriate.
5. Keep serialization in a helper if multiple receivers or tests need it.
6. Register the frontend handler from the module's realtime plugin.
7. Dispatch a `force<Verb>` store action that commits the same mutation as the
   local user action.
8. Test the backend broadcast and the frontend store update.

## Common Bugs

- Broadcasting before commit, producing UI state for rolled-back data.
- Calling the user-facing store action from a realtime handler, which repeats
  the HTTP request.
- Forgetting the frontend handler; the websocket message arrives but no state
  changes.
- Relying on realtime as the only load path. Always fetch canonical state when
  opening a page.
- Sending duplicate message types from multiple receivers without a clear
  reason.

## Related

- [Signals and `transaction.on_commit`](signals-and-on-commit.md).
- [Frontend architecture](frontend-architecture.md).
- [WebSockets](../technical/websockets.md).
- [Action system](../technical/action-system.md).
- [Optimistic updates](optimistic-updates.md).
