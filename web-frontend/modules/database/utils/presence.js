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
  }
  const spaceName = tablePresenceSpaceName(table.id)
  return { page, params, spaceName }
}

export function createPresenceFocusSender(realtime, page, parameters) {
  function send(focus) {
    realtime.sendFocus(page, parameters, focus)
  }

  function emitCellFocus(rowId, fieldId, editing = false) {
    send({ type: 'cell', row_id: rowId, field_id: fieldId, editing })
  }

  function emitRowFocus(rowId, editing = false) {
    send({ type: 'row', row_id: rowId, editing })
  }

  function clearFocus() {
    realtime.sendFocus(page, parameters, null)
  }

  return { emitCellFocus, emitRowFocus, clearFocus }
}
