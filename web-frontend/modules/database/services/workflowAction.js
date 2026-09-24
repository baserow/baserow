import { getUndoRedoActionRequestConfig } from '@baserow/modules/database/utils/action'

export default (client) => {
  return {
    fetchAll(fieldId) {
      return client.get(`database/field/${fieldId}/workflow_actions/`)
    },
    create(fieldId, values, undoRedoActionGroupId = null) {
      const config = getUndoRedoActionRequestConfig({ undoRedoActionGroupId })
      return client.post(
        `database/field/${fieldId}/workflow_actions/`,
        values,
        config
      )
    },
    update(workflowActionId, values, undoRedoActionGroupId = null) {
      const config = getUndoRedoActionRequestConfig({ undoRedoActionGroupId })
      return client.patch(
        `database/workflow_action/${workflowActionId}/`,
        values,
        config
      )
    },
    delete(workflowActionId, undoRedoActionGroupId = null) {
      const config = getUndoRedoActionRequestConfig({ undoRedoActionGroupId })
      return client.delete(
        `database/workflow_action/${workflowActionId}/`,
        config
      )
    },
    order(fieldId, workflowActionIds, undoRedoActionGroupId = null) {
      const config = getUndoRedoActionRequestConfig({ undoRedoActionGroupId })
      return client.post(
        `database/field/${fieldId}/workflow_actions/order/`,
        { workflow_action_ids: workflowActionIds },
        config
      )
    },
    dispatch(fieldId, rowId) {
      // Changes rows server side, so the clicker needs the broadcast too.
      return client.post(
        `database/field/${fieldId}/workflow_actions/dispatch/`,
        { row_id: rowId },
        { omitWebSocketId: true }
      )
    },
  }
}
