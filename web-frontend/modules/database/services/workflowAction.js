export default (client) => {
  return {
    fetchAll(fieldId) {
      return client.get(`database/field/${fieldId}/workflow_actions/`)
    },
    create(fieldId, type) {
      return client.post(`database/field/${fieldId}/workflow_actions/`, {
        type,
      })
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
      return client.post(
        `database/field/${fieldId}/workflow_actions/dispatch/`,
        { row_id: rowId }
      )
    },
  }
}
