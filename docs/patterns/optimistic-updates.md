# Optimistic updates

The reason Baserow feels fast: most write actions on the frontend
update the Vuex store **before** the HTTP request returns. If the
request fails, the action rolls back. The user sees the change
instantly; the backend gets to be eventually correct.

This is the convention across the codebase, not a per-action choice
to make. New write actions should follow the pattern unless there's a
specific reason not to (see [When not to use it](#when-not-to-use-it)
below).

For the broader frontend layering see
[Frontend architecture](frontend-architecture.md), especially the
[`<verb>` vs `force<Verb>` store split](frontend-architecture.md#store-conventions)
— that split is what makes this pattern clean.

## The mental model

The frontend has its own consistent view of the world. When the user
clicks "rename", the rename appears in the UI before the network
roundtrip; the backend is treated as the eventual reconciler. There
are three possible outcomes:

1. **Request succeeds** — the optimistic state is correct; nothing
   else to do (occasionally the response carries server-computed
   fields that need merging).
2. **Request fails** — restore the previous state and surface an
   error.
3. **Realtime event arrives meanwhile** — the realtime handler
   updates the same store via `force<Verb>`. Because the user-initiated
   path and the realtime path commit the same mutation, they don't
   fight each other; the last write wins coherently.

The whole design rests on the store having a `force<Verb>` action that
can write any state from anywhere without an HTTP call. If you don't
have that, you can't optimistically update *or* receive realtime
events cleanly. See
[Frontend architecture — store conventions](frontend-architecture.md#store-conventions).

## The canonical shape

Real example, `modules/database/store/view.js` — updating a view's
configuration:

```javascript
async update(
  { commit, dispatch },
  { view, values, readOnly = false, refreshFromFetch = false,
    optimisticUpdate = true }
) {
  const { $client, $registry } = this
  commit('SET_ITEM_LOADING', { view, value: true })

  // 1. Snapshot the old values that will change.
  const oldValues = {}
  const newValues = {}
  Object.keys(values).forEach((name) => {
    if (Object.prototype.hasOwnProperty.call(view, name)) {
      oldValues[name] = view[name]
      newValues[name] = values[name]
    }
  })

  // 2. Apply the new values immediately.
  if (optimisticUpdate) {
    dispatch('forceUpdate', { view, values: newValues, /* … */ })
  }

  // 3. Try the request.
  try {
    if (!readOnly) {
      const responseValues = (await ViewService($client).update(view.id, values)).data
      if (refreshFromFetch || !optimisticUpdate) {
        dispatch('forceUpdate', { view, values: responseValues, /* … */ })
      }
    }
    commit('SET_ITEM_LOADING', { view, value: false })
  } catch (error) {
    // 4. Roll back to the snapshot.
    commit('SET_ITEM_LOADING', { view, value: false })
    dispatch('forceUpdate', { view, values: oldValues })
    throw error
  }
}
```

The four moving parts:

1. **Snapshot**: copy whatever state is about to change. Only the
   fields actually being modified — don't copy the whole object.
2. **Apply optimistically** by dispatching `forceUpdate` (or the
   action that wraps the appropriate mutation).
3. **Call the service** inside `try`.
4. **Roll back on failure** by dispatching `forceUpdate` again with
   the snapshot, then re-throw so callers (and the global error
   handler) can react.

Notice that the service response can carry *more* than what was sent
(server-computed fields, normalised values, timestamps). The
canonical pattern lets the caller opt into reconciling those via
`refreshFromFetch = true` — useful when the backend may have
transformed the input.

## Reorder — the simpler shape

Some operations don't need a snapshot because the inverse is
explicit. View reordering:

```javascript
async order({ commit }, { table, ownershipType, order, oldOrder }) {
  const { $client } = this
  commit('ORDER_ITEMS', { ownershipType, order })

  try {
    await ViewService($client).order(table.id, ownershipType, order)
  } catch (error) {
    commit('ORDER_ITEMS', { ownershipType, order: oldOrder })
    throw error
  }
}
```

The caller passes both `order` (new) and `oldOrder` (snapshot). The
action commits the new order, fires the request, and commits the old
order on failure. No internal snapshot needed because the caller
already knows the inverse.

This works wherever the inverse is small and obvious (reordering,
toggles, deletes-with-restore). Use it instead of the snapshot
pattern when you can — fewer moving parts.

## Row value updates — the heavily-used path

Editing a cell goes through `modules/database/store/view/grid.js`
`updateRowValue` and follows the same shape. Two extra wrinkles
worth knowing:

- **Per-row task queue.** Concurrent edits to the same row are
  serialised through `createAndUpdateRowQueue.getOrCreateQueue(...)`
  so the second edit waits for the first to commit (or roll back)
  before optimistically applying. Without this, the rollback path of
  the first edit could clobber the second edit's optimistic state.
- **Group-by metadata.** When an edit changes a value that affects a
  group's row count, the optimistic path updates both: decrement the
  old group's count, apply the value, increment the new group's
  count. The rollback reverses all three. This is the kind of detail
  that makes a per-action optimistic implementation worth reading
  before writing a new one — copy `updateRowValue`'s shape, don't
  reinvent.

## Error handling

What the action does on failure:

- **Roll back** the optimistic state (always).
- **Re-throw** the error. Some flows want the action to surface
  failure (toast, form-level error, retry button); the global axios
  handler in `modules/core/plugins/clientHandler.js` already
  translates known backend errors into store dispatches for the
  toast notification system.
- **Don't swallow.** A silent rollback with no error message looks
  like a bug.

What the caller (component) does:

- Catch and decide what UI to show. For most actions, the global
  notification handler is enough — the component doesn't need to
  catch at all.
- Form-level errors (the user typed something invalid) usually need
  the component to catch so it can highlight the field. Use a
  form-component pattern with explicit error props rather than
  trying to inspect the rolled-back store state.

## Interaction with realtime

The optimistic path and the realtime path **commit the same
mutation**. If another user makes a change while your optimistic
write is in flight, the realtime handler dispatches `forceUpdate`
which lands in the store; if your request succeeds, your `forceUpdate`
overwrites; if it fails, your rollback restores the snapshot — which
may or may not match the realtime-applied state.

In practice this means:

- **Two users editing the same value at the same time** — the second
  write to land wins, both clients converge once their respective
  realtime echoes arrive.
- **Your optimistic update overrides someone else's realtime update**
  — that's by design; the user just typed and expects to see what
  they typed.
- **Rollback after a realtime update from someone else** — possible
  edge case. The rollback restores your snapshot, which may already
  be stale. If this matters in your action, fetch the current value
  from the store at rollback time instead of using the snapshot.

For the full lifecycle of a realtime event see
[Realtime end-to-end](realtime-end-to-end.md).

## When not to use it

Optimistic updates are wrong for:

- **Operations that depend on a server-computed value the user must
  see.** Creating a row that gets an autogenerated id; running a
  formula; triggering a duplicate. Wait for the response.
- **Operations with side effects the frontend can't model.** Sending
  an email, kicking off an export, deleting many things atomically.
  The user wants to know the work happened, not that we *tried*.
- **Operations where rollback would be confusing.** If the rollback
  removes data the user already saw and acted on (clicked,
  navigated), the inconsistency is worse than the wait. Better to
  show a spinner.

Default to optimistic; depart from it deliberately, with a comment
saying why.

## Anti-patterns

- **Optimistic state with no rollback.** If the request fails, the
  UI now lies. Every optimistic action must have a rollback path.
- **Rollback that re-fetches from the backend.** Slower, racier, and
  defeats the point. The snapshot is in memory; use it.
- **Snapshotting the whole object.** Only snapshot what you're about
  to change. Whole-object snapshots silently overwrite concurrent
  realtime updates to fields you didn't touch.
- **Committing mutations directly from the action instead of via
  `force<Verb>`.** The `force<Verb>` indirection is what lets
  realtime, undo, and optimistic paths share one code path. Skipping
  it diverges them.
- **Not re-throwing after rollback.** Callers can't tell the action
  failed; nothing surfaces the error to the user.

## Adding a new optimistic action

The recipe:

1. **Have a `force<Verb>` action that commits the mutation without an
   HTTP call.** If you don't have one, write it first — it's needed
   for realtime anyway.
2. **In the user-initiated action**: snapshot, dispatch `force<Verb>`
   with new values, call the service inside `try`, on error dispatch
   `force<Verb>` with the snapshot and re-throw.
3. **Decide on `optimisticUpdate` opt-out.** Most existing actions
   accept an `optimisticUpdate` flag (default `true`). Add one if the
   caller might want to skip it for read-only views, internal
   automations, or test scenarios.
4. **Reconcile the response** if the backend may transform the input
   — copy `view.js:update`'s `refreshFromFetch` pattern.
5. **Test the rollback.** Mock the axios call to fail and assert the
   store ends up in the original state. The
   [`write-frontend-unit-test` skill](https://github.com/baserow/baserow/blob/develop/.agents/skills/write-frontend-unit-test/SKILL.md)
   covers the `TestApp` + `axios-mock-adapter` setup.

## Related

- [Frontend architecture](frontend-architecture.md) — the store
  convention this depends on.
- [Frontend registries](frontend-registries.md).
- [Realtime end-to-end](realtime-end-to-end.md) — the other writer
  of `force<Verb>` actions.
- [Project conventions](../development/conventions.md) — Vue 3, `just
  f test`, en.json only.
