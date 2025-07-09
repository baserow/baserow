export default (client) => {
  return {
    create(automationId, name) {
      return client.post(`automation/${automationId}/workflows/`, {
        name,
      })
    },
    read(workflowId) {
      return client.get(`automation/workflows/${workflowId}/`)
    },
    update(workflowId, values) {
      return client.patch(`automation/workflows/${workflowId}/`, values)
    },
    delete(workflowId) {
      return client.delete(`automation/workflows/${workflowId}/`)
    },
    order(automationId, order) {
      return client.post(`/automation/${automationId}/workflows/order/`, {
        workflow_ids: order,
      })
    },
    duplicate(workflowId) {
      return client.post(`/automation/workflows/${workflowId}/duplicate/async/`)
    },
    publish(workflowId) {
      return client.post(`/automation/workflows/${workflowId}/publish/async/`)
    },
  }
}
