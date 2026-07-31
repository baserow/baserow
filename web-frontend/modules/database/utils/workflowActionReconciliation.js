import _ from 'lodash'

/**
 * Works out the API calls needed to make the server's action list match the
 * editor's local one.
 *
 * The editor buffers changes rather than saving each one, so that cancelling a
 * field edit discards them. That means the difference has to be computed at
 * submit time rather than applied as it happens.
 *
 * @param serverActions The list as the server last reported it.
 * @param localActions The list as the user has arranged it. Entries without an
 *   `id` are new.
 * @returns {{toCreate: Array, toUpdate: Array, toDelete: Array, order: Array}}
 *   `order` carries `null` where a created action's id is not known yet; the
 *   caller substitutes real ids once the creates resolve.
 */
export function reconcileWorkflowActions(serverActions, localActions) {
  const serverById = new Map(serverActions.map((a) => [a.id, a]))
  const localIds = new Set(
    localActions.filter((a) => a.id != null).map((a) => a.id)
  )

  const toCreate = localActions.filter((a) => a.id == null)

  const toUpdate = localActions
    .filter((a) => a.id != null)
    .filter((a) => !_.isEqual(a.service, serverById.get(a.id)?.service))
    .map((a) => ({ id: a.id, values: { service: a.service } }))

  const toDelete = serverActions
    .map((a) => a.id)
    .filter((id) => !localIds.has(id))

  const order = localActions.map((a) => (a.id == null ? null : a.id))

  return { toCreate, toUpdate, toDelete, order }
}
