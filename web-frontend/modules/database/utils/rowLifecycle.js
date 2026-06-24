/**
 * Shared row-lifecycle pipelines: optimistic create, update, delete,
 * and post-mutation match-flag re-evaluation.
 *
 * Callers provide:
 * - `context`: shared grid/service inputs (`client`, `registry`, `table`,
 *   `view`, `fields`, optional `groupBys`)
 * - `mutations`: store-specific row operations (`insert`, `replace`, `remove`,
 *   `applyValues`, `applyMatchFlags`, `rowsForMatchCheck`)
 *
 * The lifecycle code owns the common async flow and rollback rules; each store
 * owns where rows are inserted or patched.
 */
import RowService from '@baserow/modules/database/services/row'
import {
  buildNewRowDefaults,
  computeRowInsertPosition,
  computeRowMatchFlags,
  prepareNewOldAndUpdateRequestValues,
} from '@baserow/modules/database/utils/row'

const noop = () => {}
const emptyRows = () => []
const generateTempRowId = () => -Math.floor(Math.random() * 1e9) - 1

export function createRowLifecycleContext({
  client,
  registry,
  table,
  view,
  fields,
  groupBys = [],
  rowService = RowService(client),
}) {
  return { client, registry, table, view, fields, groupBys, rowService }
}

function resolveContext(context) {
  return context.rowService ? context : createRowLifecycleContext(context)
}

function buildInitialCreateValues(context, suppliedValues) {
  return buildNewRowDefaults({
    view: context.view,
    fields: context.fields,
    registry: context.registry,
    suppliedValues,
  })
}

function buildOptimisticRow(rowValues) {
  return {
    id: generateTempRowId(),
    ...rowValues,
    _: { loading: true },
  }
}

function prepareCreateRequestValues(context, rowValues) {
  const values = {}
  for (const field of context.fields ?? []) {
    const key = `field_${field.id}`
    if (!(key in rowValues)) {
      continue
    }

    const fieldType = context.registry.get('field', field.type)
    if (
      fieldType.canWriteFieldValues &&
      !fieldType.canWriteFieldValues(field)
    ) {
      continue
    }
    values[key] = fieldType.prepareValueForUpdate
      ? fieldType.prepareValueForUpdate(field, rowValues[key])
      : rowValues[key]
  }
  return values
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

function selectPrimaryCell(context, row, selection) {
  if (!selection.selectPrimaryCell) {
    return
  }

  const primary = (context.fields ?? []).find((field) => field.primary)
  if (primary) {
    const selectCell = selection.selectCell ?? noop
    selectCell(row.id, primary.id)
  }
}

export function createRowLifecycle(context, mutations) {
  const lifecycleContext = resolveContext(context)
  return {
    create: (options = {}) =>
      createRowOptimistically({
        context: lifecycleContext,
        mutations,
        ...options,
      }),
    update: (options) =>
      updateRowOptimistically({
        context: lifecycleContext,
        mutations,
        ...options,
      }),
    delete: (options) =>
      deleteRowOptimistically({
        context: lifecycleContext,
        mutations,
        ...options,
      }),
    reapplyMatchFlags: (options) =>
      reapplyMatchFlags({
        context: lifecycleContext,
        mutations,
        ...options,
      }),
  }
}

/**
 * Optimistic create: insert a temporary loading row, POST, replace it with
 * the backend row, then re-evaluate match flags. Rolls back on errors and on
 * empty backend responses.
 */
export async function createRowOptimistically({
  context,
  mutations,
  suppliedValues = {},
  beforeId = null,
  selection = {},
}) {
  const lifecycleContext = resolveContext(context)
  const initialValues = buildInitialCreateValues(
    lifecycleContext,
    suppliedValues
  )
  const optimisticRow = buildOptimisticRow(initialValues)

  mutations.insert(optimisticRow, optimisticRow.id)

  let beRow = null
  try {
    const response = await lifecycleContext.rowService.create(
      lifecycleContext.table.id,
      prepareCreateRequestValues(lifecycleContext, initialValues),
      beforeId,
      lifecycleContext.view.id
    )
    beRow = response?.data ?? null
  } catch (error) {
    mutations.remove(optimisticRow.id)
    throw error
  }

  if (!beRow) {
    mutations.remove(optimisticRow.id)
    return null
  }

  mutations.replace(optimisticRow.id, beRow)
  applyCurrentMatchFlags(lifecycleContext, beRow, mutations)
  selectPrimaryCell(lifecycleContext, beRow, selection)
  return beRow
}

/**
 * Optimistic single-cell update: apply the edited value immediately, PATCH,
 * layer the backend row over the optimistic state, then re-evaluate match
 * flags. Rolls back to the old values on backend errors.
 */
export async function updateRowOptimistically({ context, mutations, edit }) {
  const lifecycleContext = resolveContext(context)
  const { row, field, value, oldValue } = edit
  const { newRowValues, oldRowValues, updateRequestValues } =
    prepareNewOldAndUpdateRequestValues(
      row,
      lifecycleContext.fields,
      field,
      value,
      oldValue,
      lifecycleContext.registry
    )
  const rowId = row.id

  mutations.applyValues(rowId, newRowValues)

  let beRow = null
  try {
    const response = await lifecycleContext.rowService.batchUpdate(
      lifecycleContext.table.id,
      [updateRequestValues],
      null,
      lifecycleContext.view.id
    )
    const items = response?.data?.items ?? []
    beRow = items.find((item) => item.id === rowId) ?? items[0] ?? null
  } catch (error) {
    mutations.applyValues(rowId, oldRowValues)
    throw error
  }

  if (beRow) {
    mutations.applyValues(rowId, beRow)
    applyCurrentMatchFlags(lifecycleContext, beRow, mutations)
  }
  return beRow
}

/**
 * Optimistic delete: remove locally, DELETE, then re-insert the original row
 * if the backend call fails.
 */
export async function deleteRowOptimistically({ context, mutations, row }) {
  if (!row || row.id == null) {
    return false
  }

  const lifecycleContext = resolveContext(context)
  mutations.remove(row.id)
  try {
    await lifecycleContext.rowService.delete(
      lifecycleContext.table.id,
      row.id,
      lifecycleContext.view?.id ?? null
    )
    return true
  } catch (error) {
    const insert = mutations.insert ?? noop
    insert(row, row.id)
    throw error
  }
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
