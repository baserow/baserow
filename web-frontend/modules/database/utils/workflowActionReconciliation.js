import _ from 'lodash'

/**
 * Works out the API calls needed to make the server's action list match the
 * editor's local one.
 *
 * The editor buffers changes rather than saving each one, so that cancelling a
 * field edit discards them. That means the difference has to be computed at
 * submit time rather than applied as it happens.
 *
 * An entry carrying an `id` is assumed to keep the same `type` for its
 * lifetime: the editor offers no way to change an existing action's type,
 * only to delete it and add a new one. Because of that, `toUpdate` compares
 * only `service`, never `type`. If a type dropdown for existing actions is
 * ever added, this function must be revisited to also diff `type`.
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

    if (!_.isEqual(action.service, serverAction.service)) {
      toUpdate.push({ id: action.id, values: { service: action.service } })
    }
  })

  const toDelete = serverActions
    .map((a) => a.id)
    .filter((id) => !keptIds.has(id))

  return { toCreate, toUpdate, toDelete, order }
}
