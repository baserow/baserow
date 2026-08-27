import _ from 'lodash'
import { referencedActionIds } from '@baserow/modules/database/utils/workflowActionFormulas'

// Keys the API owns. Everything else is the type's own config.
const API_OWNED_KEYS = ['id', 'type', 'order', 'field_id']

// How the editor tells one unsaved action from another, before the server has
// given it an id. Never sent, and never part of a diff against the server.
export const CLIENT_ID_KEY = '_clientId'

/**
 * What identifies an action in the editor, saved or not. Its position cannot
 * stand in for one: deleting the action above would hand its identity, and so
 * its form state and any reference to it, to the one below.
 */
export function workflowActionKey(action) {
  return action.id ?? action[CLIENT_ID_KEY]
}

/**
 * The type specific config of an action, without the keys the API owns. Used
 * both to diff two actions and to build the payload that persists one.
 */
export function workflowActionConfig(action) {
  return _.omit(action, [...API_OWNED_KEYS, CLIENT_ID_KEY])
}

/**
 * Every action this one's formulas reference. The same keys as
 * `workflowActionConfig`, walked where they are: `_.omit` deep copies what it
 * keeps, which on a wide table is the whole saved schema, and this only reads.
 */
export function referencedActionIdsInConfig(action) {
  const found = new Set()
  Object.entries(action).forEach(([key, value]) => {
    if (!API_OWNED_KEYS.includes(key) && key !== CLIENT_ID_KEY) {
      referencedActionIds(value, found)
    }
  })
  return [...found]
}

/**
 * Works out the API calls needed to make the server's action list match the
 * editor's local one. The editor buffers changes so that cancelling discards
 * them, which means the difference has to be computed at submit time.
 *
 * A changed `type` is sent with the whole config, because the server implements
 * it as a delete plus a create. That hands back a new id, which the caller has
 * to substitute into `order`.
 *
 * @param serverActions The list as the server last reported it.
 * @param localActions The list as the user has arranged it. Entries without an
 *   `id`, or with an `id` the server does not recognise, are new.
 * @returns {{toCreate: Array, toUpdate: Array, toDelete: Array, order: Array}}
 *   `order` carries `null` where a created action's id is not known yet.
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
      // No id, or one the server no longer knows: treat as new and strip it.
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
