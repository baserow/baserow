/**
 * Shared row-lifecycle pipelines: optimistic create, update, delete,
 * and the post-mutation match-flag re-evaluation. Both the flat grid
 * and the grouped grid need identical behaviour (same loading
 * spinner, same "row has moved" warning, same BE payload shape, same
 * rollback rules); only the *state-write* (where to put the row)
 * differs between them.
 *
 * Each function below takes a small set of adapter callbacks that the
 * caller's store implements. The store passes:
 *
 *   - `insert(row, tempId)`      — put the optimistic row somewhere
 *                                  the user will see immediately
 *                                  (flat buffer / per-section bucket)
 *   - `replace(tempId, beRow)`   — swap the optimistic row for the
 *                                  BE-confirmed one (same position)
 *   - `remove(tempId)`           — rollback: pull the optimistic row
 *                                  back out
 *   - `applyValues(rowId, patch)`— in-place value update (used by the
 *                                  optimistic phase of updates and
 *                                  the BE-confirm phase to layer the
 *                                  authoritative response on top)
 *   - `applyMatchFlags(rowId, flags)`
 *                                — patch `_.matchFilters` /
 *                                  `_.matchSortings` so the row picks
 *                                  up the "row has moved" / "row
 *                                  doesn't match filters" warnings
 *   - `rowsForMatchCheck(row)`   — lazy callback returning the rows
 *                                  to sort against when evaluating
 *                                  `matchSortings`; only invoked when
 *                                  match-flag eval actually runs
 *
 * Keeping the pipeline general means the two grids stay in lockstep
 * automatically — adding a feature here makes both grids gain it.
 *
 * Migration note: the grouped grid uses these helpers today. The flat
 * grid's `view/grid/createNewRow` / `updateRowValue` /
 * `deletedExistingRow` actions still inline equivalent logic and
 * should switch to these helpers in a follow-up PR so the two paths
 * can never diverge.
 */
import RowService from '@baserow/modules/database/services/row'
import {
  buildNewRowDefaults,
  computeRowMatchFlags,
  prepareNewOldAndUpdateRequestValues,
} from '@baserow/modules/database/utils/row'

const generateTempRowId = () => -Math.floor(Math.random() * 1e9) - 1

/**
 * Optimistic create: build the row, insert with a spinner, POST, then
 * swap for the BE row and evaluate match flags. Rolls back on
 * failure.
 *
 * Returns the BE row on success, or `null` if the response had no
 * data. Throws (after rollback) on a BE error.
 */
export async function createRowOptimistically({
  client,
  registry,
  table,
  view,
  fields,
  suppliedValues = {},
  beforeId = null,
  insert,
  replace,
  remove,
  applyMatchFlags = () => {},
  rowsForMatchCheck = () => [],
  groupBys = [],
  selectPrimaryCell = false,
  selectCell = () => {},
}) {
  const optimisticValues = buildNewRowDefaults({
    view,
    fields,
    registry,
    suppliedValues,
  })
  const tempId = generateTempRowId()
  const optimisticRow = {
    id: tempId,
    ...optimisticValues,
    _: { loading: true },
  }

  insert(optimisticRow, tempId)

  const beValues = {}
  for (const f of fields ?? []) {
    const key = `field_${f.id}`
    if (!(key in suppliedValues)) continue
    const fieldType = registry.get('field', f.type)
    beValues[key] = fieldType.prepareValueForUpdate
      ? fieldType.prepareValueForUpdate(f, suppliedValues[key])
      : suppliedValues[key]
  }

  let beRow = null
  try {
    const response = await RowService(client).create(
      table.id,
      beValues,
      beforeId,
      view.id
    )
    beRow = response?.data ?? null
  } catch (error) {
    remove(tempId)
    throw error
  }

  if (beRow) {
    replace(tempId, beRow)
    const flags = computeRowMatchFlags({
      row: beRow,
      view,
      fields,
      registry,
      rowsInSortingGroup: rowsForMatchCheck(beRow),
      groupBys,
    })
    applyMatchFlags(beRow.id, flags)
    // Auto-select the primary cell of the new row so the standard
    // unselect → re-apply filters flow fires when the user clicks
    // elsewhere — matches the flat grid's `selectPrimaryCell` flag.
    if (selectPrimaryCell) {
      const primary = (fields ?? []).find((f) => f.primary)
      if (primary) selectCell(beRow.id, primary.id)
    }
  }
  return beRow
}

/**
 * Optimistic single-cell update: apply the new values locally, PATCH
 * via `RowService.batchUpdate`, then layer the BE response on top and
 * re-evaluate match flags. Rolls back to `oldValue` on failure.
 *
 * Caller supplies `row`, the edited `field`, the new `value`, and the
 * pre-edit `oldValue` — same shape `GridViewCell` already emits via
 * its `@update` event, so wiring is uniform across grids.
 *
 * Returns the merged BE row data on success. Throws (after rollback)
 * on a BE error.
 */
export async function updateRowOptimistically({
  client,
  registry,
  table,
  view,
  fields,
  row,
  field,
  value,
  oldValue,
  applyValues,
  applyMatchFlags = () => {},
  rowsForMatchCheck = () => [],
  groupBys = [],
}) {
  const { newRowValues, oldRowValues, updateRequestValues } =
    prepareNewOldAndUpdateRequestValues(
      row,
      fields,
      field,
      value,
      oldValue,
      registry
    )
  const rowId = row.id

  // 1. Optimistic write locally.
  applyValues(rowId, newRowValues)

  // 2. PATCH.
  let beRow = null
  try {
    const response = await RowService(client).batchUpdate(
      table.id,
      [updateRequestValues],
      null,
      view.id
    )
    const items = response?.data?.items ?? []
    beRow = items.find((r) => r.id === rowId) ?? items[0] ?? null
  } catch (error) {
    applyValues(rowId, oldRowValues)
    throw error
  }

  // 3. Layer BE response on top of the optimistic row + re-evaluate.
  if (beRow) {
    applyValues(rowId, beRow)
    const flags = computeRowMatchFlags({
      row: beRow,
      view,
      fields,
      registry,
      rowsInSortingGroup: rowsForMatchCheck(beRow),
      groupBys,
    })
    applyMatchFlags(rowId, flags)
  }
  return beRow
}

/**
 * Optimistic delete: remove locally, DELETE via the BE, rollback by
 * re-inserting on failure. The caller's `insert` is reused for the
 * rollback path — same shape `createRowOptimistically` uses.
 *
 * Returns `true` on success, `false` if the caller didn't supply a
 * row. Throws (after rollback) on a BE error.
 */
export async function deleteRowOptimistically({
  client,
  table,
  row,
  remove,
  insert,
}) {
  if (!row || row.id == null) return false
  remove(row.id)
  try {
    await RowService(client).delete(table.id, row.id)
    return true
  } catch (error) {
    if (insert) insert(row, row.id)
    throw error
  }
}

/**
 * Re-evaluate `matchFilters` + `matchSortings` for `row` against the
 * caller-supplied comparison set, and apply the result via
 * `applyMatchFlags`. Used after a row update commits, or after the
 * user unselects, to surface the "row has moved" warning when the
 * BE-truth position no longer agrees with where the row is rendered.
 *
 * This is a sync wrapper around `computeRowMatchFlags` — kept as a
 * named export so callers don't have to know the flag computation
 * happens elsewhere; they just call the lifecycle module.
 */
export function reapplyMatchFlags({
  registry,
  row,
  view,
  fields,
  applyMatchFlags,
  rowsForMatchCheck = () => [],
  groupBys = [],
}) {
  if (!row) return
  const flags = computeRowMatchFlags({
    row,
    view,
    fields,
    registry,
    rowsInSortingGroup: rowsForMatchCheck(row),
    groupBys,
  })
  applyMatchFlags(row.id, flags)
}
