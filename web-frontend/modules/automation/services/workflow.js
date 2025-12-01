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
    getHistory(workflowId) {
      return client.get(`automation/workflows/${workflowId}/history/`)
    },
    update(workflowId, values) {
      return client.patch(`automation/workflows/${workflowId}/`, values)
    },
    delete(workflowId) {
      return client.delete(`automation/workflows/${workflowId}/`)
    },
    order(workflowId, nodeIds) {
      return client.post(`/automation/workflows/${workflowId}/nodes/order/`, {
        node_ids: nodeIds,
      })
    },
    duplicate(workflowId) {
      return client.post(`/automation/workflows/${workflowId}/duplicate/async/`)
    },
    publish(workflowId) {
      return client.post(`/automation/workflows/${workflowId}/publish/async/`)
    },
    testRun(workflowId) {
      return client.post(`/automation/workflows/${workflowId}/test/`)
    },
  }
}
