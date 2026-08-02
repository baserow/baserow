import _ from 'lodash'

// The keys an action carries that belong to the API rather than to the
// editor. Everything else is the type's own config: `service` for the row
// actions, `url` and `target` for `open_url`.
const API_OWNED_KEYS = ['id', 'type', 'order', 'field_id']

/**
 * The type specific config of an action, without the keys the API owns. Used
 * both to diff two actions and to build the payload that persists one.
 */
export function workflowActionConfig(action) {
  return _.omit(action, API_OWNED_KEYS)
}

/**
 * Works out the API calls needed to make the server's action list match the
 * editor's local one.
 *
 * The editor buffers changes rather than saving each one, so that cancelling a
 * field edit discards them. That means the difference has to be computed at
 * submit time rather than applied as it happens.
 *
 * An entry carrying an `id` may have changed `type`: the editor offers a type
 * dropdown per row. A changed type is sent together with the new type's whole
 * config, because the server implements a type change as a delete plus a
 * create and needs everything in one payload. It also hands back a **new id**,
 * which the caller has to substitute into `order`.
 *
 * A row whose `type` is still `null` is a row the user added but has not
 * chosen a type for yet. It is not an action: it produces no call and takes no
 * slot in the order.
 *
 * A local id the server does not recognise (e.g. gone stale) is treated as a
 * new action rather than issuing an update against a nonexistent id: it is
 * stripped of its id and placed in `toCreate`, with a `null` order slot,
 * exactly like a brand new action would be.
 *
 * @param serverActions The list as the server last reported it.
 * @param localActions The list as the user has arranged it. Entries without an
 *   `id`, or with an `id` the server does not recognise, are new.
 * @returns {{toCreate: Array, toUpdate: Array, toDelete: Array, order: Array}}
 *   `order` carries `null` where a created action's id is not known yet; the
 *   caller substitutes real ids once the creates resolve.
 */
export function reconcileWorkflowActions(serverActions, localActions) {
  const serverById = new Map(serverActions.map((a) => [a.id, a]))

  const toCreate = []
  const toUpdate = []
  const order = []
  const keptIds = new Set()

  localActions.forEach((action) => {
    if (action.type == null) {
      // A row the user added but has not picked a type for yet.
      return
    }

    const serverAction =
      action.id == null ? undefined : serverById.get(action.id)

    if (serverAction === undefined) {
      // No id, or an id the server no longer knows: treat as new. Strip the
      // id so the caller never sends a stale one back to the server.
      const { id, ...withoutId } = action
      toCreate.push(withoutId)
      order.push(null)
      return
    }

    keptIds.add(action.id)
    order.push(action.id)

    const config = workflowActionConfig(action)
    const typeChanged = action.type !== serverAction.type

    if (typeChanged) {
      toUpdate.push({ id: action.id, values: { type: action.type, ...config } })
    } else if (!_.isEqual(config, workflowActionConfig(serverAction))) {
      toUpdate.push({ id: action.id, values: config })
    }
  })

  const toDelete = serverActions
    .map((a) => a.id)
    .filter((id) => !keptIds.has(id))

  return { toCreate, toUpdate, toDelete, order }
}
