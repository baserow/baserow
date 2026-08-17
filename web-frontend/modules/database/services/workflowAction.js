export default (client) => {
  return {
    fetchAll(fieldId) {
      return client.get(`database/field/${fieldId}/workflow_actions/`)
    },
    create(fieldId, values) {
      return client.post(`database/field/${fieldId}/workflow_actions/`, values)
    },
    update(workflowActionId, values) {
      return client.patch(
        `database/workflow_action/${workflowActionId}/`,
        values
      )
    },
    delete(workflowActionId) {
      return client.delete(`database/workflow_action/${workflowActionId}/`)
    },
    order(fieldId, workflowActionIds) {
      return client.post(`database/field/${fieldId}/workflow_actions/order/`, {
        workflow_action_ids: workflowActionIds,
      })
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
