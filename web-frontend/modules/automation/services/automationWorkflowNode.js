export default (client) => {
  return {
    create(workflowId, type, beforeId = null) {
      const payload = { type }
      if (beforeId !== null) {
        payload.before_id = beforeId
      }
      return client.post(`automation/workflow/${workflowId}/nodes/`, payload)
    },
    get(workflowId) {
      return client.get(`automation/workflow/${workflowId}/nodes/`)
    },
    update(nodeId, values) {
      return client.patch(`automation/node/${nodeId}/`, values)
    },
    delete(nodeId) {
      return client.delete(`automation/node/${nodeId}/`)
    },
    order(workflowId, order) {
      return client.post(`/automation/workflow/${workflowId}/order/`, {
        node_ids: order,
      })
    },
    replace(nodeId, values) {
      return client.post(`automation/node/${nodeId}/replace/`, values)
    },
  }
}
