/**
 * Canonical frontend source for the table presence space name format.
 * Mirrors backend table_presence_space_name() in database/ws/pages.py.
 */
export function tablePresenceSpaceName(tableId) {
  return `table-${tableId}`
}

/**
 * Resolves the realtime page, parameters, and presence space name for
 * presence focus emission. Handles viewOwnershipType enhancement
 * (e.g. restricted_view overrides).
 */
export function resolvePresencePageParams(registry, database, table, view) {
  let page = 'table'
  let params = { table_id: table.id }
  let focusEnabled = true
  if (view) {
    const ownershipType = registry.get('viewOwnershipType', view.ownership_type)
    const result = ownershipType.enhanceRealtimePagePayload(
      database,
      table,
      view,
      { page, params }
    )
    page = result.page
    params = result.params
    focusEnabled = ownershipType.supportsPresenceFocus(database, table, view)
  }
  const spaceName = tablePresenceSpaceName(table.id)
  return { page, params, spaceName, focusEnabled }
}

const NAVIGATION_DEBOUNCE_MS = 150

export function createPresenceFocusSender(
  realtime,
  page,
  parameters,
  { hasOtherMembers } = {}
) {
  let lastFocus = null
  let lastEditing = false
  let debounceTimer = null

  function send(focus) {
    lastFocus = focus
    if (hasOtherMembers && !hasOtherMembers()) {
      return
    }
    realtime.sendFocus(page, parameters, focus)
  }

  function sendDebounced(focus) {
    lastFocus = focus
    if (hasOtherMembers && !hasOtherMembers()) {
      return
    }
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      realtime.sendFocus(page, parameters, focus)
    }, NAVIGATION_DEBOUNCE_MS)
  }

  function reemitLastFocus() {
    if (lastFocus !== null) {
      realtime.sendFocus(page, parameters, lastFocus)
    }
  }

  function emitCellFocus(rowId, fieldId, editing = false) {
    const focus = { type: 'cell', row_id: rowId, field_id: fieldId, editing }
    if (editing !== lastEditing) {
      lastEditing = editing
      clearTimeout(debounceTimer)
      send(focus)
    } else {
      sendDebounced(focus)
    }
  }

  function emitRowFocus(rowId, editing = false) {
    const focus = { type: 'row', row_id: rowId, editing }
    if (editing !== lastEditing) {
      lastEditing = editing
      clearTimeout(debounceTimer)
      send(focus)
    } else {
      sendDebounced(focus)
    }
  }

  function clearFocus() {
    clearTimeout(debounceTimer)
    lastEditing = false
    send(null)
  }

  function destroy() {
    clearTimeout(debounceTimer)
  }

  return { emitCellFocus, emitRowFocus, clearFocus, reemitLastFocus, destroy }
}
