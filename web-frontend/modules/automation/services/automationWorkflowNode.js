export default (client) => {
  return {
    create(workflowId, type, referenceNode, position, output, config = {}) {
      const payload = { type }
      if (referenceNode) {
        payload.reference_node_id = referenceNode.id
        payload.position = position
        payload.output = output
      }
      return client.post(
        `automation/workflow/${workflowId}/nodes/`,
        payload,
        config
      )
    },
    get(workflowId) {
      return client.get(`automation/workflow/${workflowId}/nodes/`)
    },
    update(nodeId, values, config = {}) {
      return client.patch(`automation/node/${nodeId}/`, values, config)
    },
    delete(nodeId, config = {}) {
      return client.delete(`automation/node/${nodeId}/`, config)
    },
    move(nodeId, values) {
      return client.post(`automation/node/${nodeId}/move/`, values)
    },
    replace(nodeId, values) {
      return client.post(`automation/node/${nodeId}/replace/`, values)
    },
    simulateDispatch(nodeId) {
      return client.post(`automation/node/${nodeId}/simulate-dispatch/`)
    },
    duplicate(nodeId) {
      return client.post(`automation/node/${nodeId}/duplicate/`)
    },
  }
}
