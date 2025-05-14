export default (client) => {
  return {
    create(workflowId, type) {
      return client.post(`automation/workflow/${workflowId}/nodes/`, {
        type,
      })
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
  }
}
