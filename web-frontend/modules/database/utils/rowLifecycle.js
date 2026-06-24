/**
 * Shared row-lifecycle helpers for row visibility, positioning, and
 * post-mutation match-flag re-evaluation.
 *
 * Callers provide:
 * - `context`: shared grid inputs (`client`, `registry`, `table`, `view`,
 *   `fields`, optional `groupBys`)
 * - `mutations`: store-specific row operations (`insertAtPosition`,
 *   `replaceAtPosition`, `remove`, `applyMatchFlags`, `rowsForMatchCheck`)
 *
 * The lifecycle code owns the common decision rules; the store owns where rows
 * are inserted or patched.
 */
import {
  computeRowInsertPosition,
  computeRowMatchFlags,
} from '@baserow/modules/database/utils/row'

const noop = () => {}
const emptyRows = () => []

export function createRowLifecycleContext({
  registry,
  view,
  fields,
  groupBys = [],
}) {
  return { registry, view, fields, groupBys }
}

function resolveContext(context) {
  return context.groupBys === undefined ? { ...context, groupBys: [] } : context
}

function applyCurrentMatchFlags(context, row, mutations) {
  const rowsForMatchCheck = mutations.rowsForMatchCheck ?? emptyRows
  const flags = computeRowMatchFlags({
    row,
    view: context.view,
    fields: context.fields,
    registry: context.registry,
    rowsInSortingGroup: rowsForMatchCheck(row),
    groupBys: context.groupBys,
  })

  const applyMatchFlags = mutations.applyMatchFlags ?? noop
  applyMatchFlags(row.id, flags)
  return flags
}

/**
 * Re-evaluate `matchFilters` and `matchSortings` for a row and apply the
 * resulting warning flags through the caller's store adapter.
 */
export function reapplyMatchFlags({ context, mutations, row }) {
  if (!row) {
    return
  }
  applyCurrentMatchFlags(resolveContext(context), row, mutations)
}

/**
 * Handle a row that was deleted externally (e.g. via a real-time event).
 * Removes the row only if it was visible in the current view.
 */
export function handleRowDeleted({ context, mutations, row }) {
  const lifecycleContext = resolveContext(context)

  const flags = computeRowMatchFlags({
    row,
    view: lifecycleContext.view,
    fields: lifecycleContext.fields,
    registry: lifecycleContext.registry,
    rowsInSortingGroup: (mutations.rowsForMatchCheck ?? emptyRows)(row),
    groupBys: lifecycleContext.groupBys,
  })

  if (!flags.matchFilters) {
    return
  }

  mutations.remove(row.id)
}

/**
 * Handle a row that was updated externally (e.g. via a real-time event).
 *
 * Four cases based on whether the old and new row match the current view:
 *
 * | oldRow in view | newRow in view | Action                                |
 * |----------------|----------------|---------------------------------------|
 * | yes            | no             | remove                                |
 * | no             | yes            | insertAtPosition + applyMatchFlags    |
 * | no             | no             | noop                                  |
 * | yes            | yes            | replaceAtPosition + applyMatchFlags   |
 */
export function handleRowUpdated({ context, mutations, oldRow, newRow }) {
  const lifecycleContext = resolveContext(context)

  const oldFlags = computeRowMatchFlags({
    row: oldRow,
    view: lifecycleContext.view,
    fields: lifecycleContext.fields,
    registry: lifecycleContext.registry,
    rowsInSortingGroup: (mutations.rowsForMatchCheck ?? emptyRows)(oldRow),
    groupBys: lifecycleContext.groupBys,
  })

  // Compute newRow flags using rows that exclude newRow itself, so the row
  // is not compared against its own position when deciding where it belongs.
  const rowsExcludingNew = (mutations.rowsForMatchCheck ?? emptyRows)(
    newRow
  ).filter((r) => r.id !== newRow.id)
  const newFlags = computeRowMatchFlags({
    row: newRow,
    view: lifecycleContext.view,
    fields: lifecycleContext.fields,
    registry: lifecycleContext.registry,
    rowsInSortingGroup: rowsExcludingNew,
    groupBys: lifecycleContext.groupBys,
  })

  const wasInView = oldFlags.matchFilters
  const isInView = newFlags.matchFilters

  if (wasInView && !isInView) {
    // Row moved out of the view — remove it.
    mutations.remove(newRow.id)
  } else if (!wasInView && isInView) {
    // Row moved into the view — insert at its new position.
    const position = computeRowInsertPosition(
      newRow,
      rowsExcludingNew,
      lifecycleContext.view.sortings ?? [],
      lifecycleContext.fields,
      lifecycleContext.registry,
      lifecycleContext.groupBys
    )
    mutations.insertAtPosition(newRow, position)
    const applyMatchFlags = mutations.applyMatchFlags ?? noop
    applyMatchFlags(newRow.id, newFlags)
  } else if (!wasInView && !isInView) {
    // Row was not and is still not visible — nothing to do.
  } else {
    // Row stays in the view — update its position and flags.
    const position = computeRowInsertPosition(
      newRow,
      rowsExcludingNew,
      lifecycleContext.view.sortings ?? [],
      lifecycleContext.fields,
      lifecycleContext.registry,
      lifecycleContext.groupBys
    )
    mutations.replaceAtPosition(newRow.id, newRow, position)
    const applyMatchFlags = mutations.applyMatchFlags ?? noop
    applyMatchFlags(newRow.id, newFlags)
  }
}

/**
 * Handle a row that was created externally (e.g. via a real-time event).
 * Inserts the row only if it matches the current view; skips silently otherwise.
 */
export function handleRowCreated({ context, mutations, row }) {
  const lifecycleContext = resolveContext(context)
  const existingRows = (mutations.rowsForMatchCheck ?? emptyRows)(row)

  const flags = computeRowMatchFlags({
    row,
    view: lifecycleContext.view,
    fields: lifecycleContext.fields,
    registry: lifecycleContext.registry,
    rowsInSortingGroup: existingRows,
    groupBys: lifecycleContext.groupBys,
  })

  if (!flags.matchFilters) {
    return
  }

  const position = computeRowInsertPosition(
    row,
    existingRows,
    lifecycleContext.view.sortings ?? [],
    lifecycleContext.fields,
    lifecycleContext.registry,
    lifecycleContext.groupBys
  )

  mutations.insertAtPosition(row, position)
  const applyMatchFlags = mutations.applyMatchFlags ?? noop
  applyMatchFlags(row.id, flags)
}
