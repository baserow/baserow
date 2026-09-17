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
 * How many undo steps the calls for `plan` can register. Counts the most a save
 * can send: an update that changes the type and its config is two calls, and an
 * order call is counted whenever there is a list to order.
 */
export function countUndoSteps({ toCreate, toUpdate, toDelete, order }) {
  const updates = toUpdate.reduce(
    (count, { values }) =>
      count + (values.type !== undefined && 'service' in values ? 2 : 1),
    0
  )
  return (
    toCreate.length + updates + toDelete.length + (order.length > 0 ? 1 : 0)
  )
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
      // No id, or one the server no longer knows: treat as new. The id it had
      // is kept rather than stripped, because the actions after it name it by
      // that id and have to follow it to the one it is created under. It never
      // reaches the API: `workflowActionConfig` leaves it out of the payload.
      toCreate.push(action)
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

/**
 * Carries the editor's unsaved edits over onto a list that changed on the
 * server since the editor read it, by an undo or a collaborator. Keeping the
 * old buffer instead would make the next save put back whatever changed.
 *
 * An action the user did not touch follows the server: it takes the server's
 * version, or goes when the server no longer has it. An action the user
 * changed or added keeps the user's version. An action the server gained is
 * added at its server position, and one the user removed stays removed.
 *
 * @param base The list the editor's buffer was taken from.
 * @param fresh The list as the server has it now.
 * @param local The editor's buffer.
 * @returns The buffer to edit from here on.
 */
export function rebaseWorkflowActions(base, fresh, local) {
  const baseById = new Map(base.map((a) => [a.id, a]))
  const freshById = new Map(fresh.map((a) => [a.id, a]))

  const result = []
  local.forEach((action) => {
    const baseAction = action.id == null ? undefined : baseById.get(action.id)
    const touched =
      baseAction === undefined ||
      action.type !== baseAction.type ||
      !_.isEqual(workflowActionConfig(action), workflowActionConfig(baseAction))
    if (touched) {
      result.push(action)
    } else if (freshById.has(action.id)) {
      result.push(_.cloneDeep(freshById.get(action.id)))
    }
  })

  const localIds = new Set(local.map((a) => a.id).filter((id) => id != null))
  fresh.forEach((action, index) => {
    if (baseById.has(action.id) || localIds.has(action.id)) {
      return
    }
    // After the nearest action before it on the server that is still listed.
    const previous = fresh
      .slice(0, index)
      .reverse()
      .find((candidate) => result.some((a) => a.id === candidate.id))
    const at = previous ? result.findIndex((a) => a.id === previous.id) + 1 : 0
    result.splice(at, 0, _.cloneDeep(action))
  })

  return result
}
