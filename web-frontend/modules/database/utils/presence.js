import { FF_USER_PRESENCE } from '@baserow/modules/core/plugins/featureFlags'

/**
 * Canonical frontend source for the table presence space name format.
 * Mirrors backend table_presence_space_name() in database/ws/pages.py.
 */
export function tablePresenceSpaceName(tableId) {
  return `table-${tableId}`
}

/**
 * Whether user presence is active for this client. Requires both the
 * `user_presence` feature flag (rollout gate, removed at GA) and the
 * BASEROW_ENABLE_USER_PRESENCE runtime config circuit breaker (string
 * 'true'/'false', defaulted to 'true' in the core module). The backend
 * enforces the same pair authoritatively; this check only skips presence UI
 * and focus emitter setup. See docs/technical/realtime-presence.md.
 */
export function isUserPresenceEnabled(vm) {
  return (
    typeof vm.$featureFlagIsEnabled === 'function' &&
    vm.$featureFlagIsEnabled(FF_USER_PRESENCE) &&
    vm.$config?.public?.baserowEnableUserPresence === 'true'
  )
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

/**
 * Creates a sender that broadcasts the current user's focus (selected cell or
 * row) over the realtime connection. Non-null focus emissions are debounced
 * during navigation and suppressed while `hasOtherMembers` returns false, so
 * solo users generate no traffic. The sender tracks what was actually
 * transmitted (`sentFocus`) so that a clear is sent if and only if remote
 * state exists, even when the user is alone by then.
 *
 * @param {object} realtime Realtime handler exposing
 *   `sendFocus(page, parameters, focus)`.
 * @param {string} page The realtime page name to emit on.
 * @param {object} parameters The realtime page parameters.
 * @param {object} [options]
 * @param {() => boolean} [options.hasOtherMembers] When provided, non-null
 *   focus is only transmitted while it returns true.
 * @returns {{
 *   emitCellFocus: (rowId: number, fieldId: number, editing?: boolean) => void,
 *   emitRowFocus: (rowId: number, editing?: boolean) => void,
 *   clearFocus: () => void,
 *   reemitLastFocus: () => void,
 *   destroy: () => void,
 * }}
 */
export function createPresenceFocusSender(
  realtime,
  page,
  parameters,
  { hasOtherMembers } = {}
) {
  let lastFocus = null
  let sentFocus = null
  let lastEditing = false
  let debounceTimer = null

  function transmit(focus) {
    sentFocus = focus
    realtime.sendFocus(page, parameters, focus)
  }

  function isGated() {
    return hasOtherMembers && !hasOtherMembers()
  }

  function send(focus) {
    lastFocus = focus
    if (isGated()) {
      // An armed timer holds an older payload; letting it fire after the last
      // member left would transmit stale focus while alone.
      clearTimeout(debounceTimer)
      return
    }
    transmit(focus)
  }

  function sendDebounced(focus) {
    lastFocus = focus
    clearTimeout(debounceTimer)
    if (isGated()) {
      return
    }
    debounceTimer = setTimeout(() => {
      transmit(focus)
    }, NAVIGATION_DEBOUNCE_MS)
  }

  function reemitLastFocus() {
    if (lastFocus === null || isGated()) {
      return
    }
    transmit(lastFocus)
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
    lastFocus = null
    lastEditing = false
    // A transmitted focus lives in server-side presence state that new
    // joiners receive, so the clear must bypass the hasOtherMembers gate;
    // conversely nothing needs to go out if nothing was ever transmitted.
    if (sentFocus !== null) {
      transmit(null)
    }
  }

  function destroy() {
    clearTimeout(debounceTimer)
  }

  return {
    emitCellFocus,
    emitRowFocus,
    clearFocus,
    reemitLastFocus,
    destroy,
  }
}
