export default (client) => {
  return {
    create(
      workflowId,
      type,
      beforeId = null,
      previousNodeId = null,
      previousNodeOutput = null
    ) {
      const payload = { type }
      if (beforeId !== null) {
        payload.before_id = beforeId
      }
      if (previousNodeId !== null) {
        payload.previous_node_id = previousNodeId
      }
      if (previousNodeOutput !== null) {
        payload.previous_node_output = previousNodeOutput
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
    move(nodeId, values) {
      return client.post(`automation/node/${nodeId}/move/`, values)
    },
    replace(nodeId, values) {
      return client.post(`automation/node/${nodeId}/replace/`, values)
    },
    simulateDispatch(nodeId) {
      return client.post(`automation/node/${nodeId}/simulate-dispatch/`)
    },
  }
}
