export default (client) => {
  return {
    getWorkflowHistory(workflowId) {
      return client.get(`automation/workflows/${workflowId}/history/`)
    },
    getNodeHistories(workflowHistoryId, parentNodeId = null) {
      const params = {}
      if (parentNodeId !== null && parentNodeId !== undefined) {
        params.parent_node_id = parentNodeId
      }
      return client.get(
        `automation/workflow_histories/${workflowHistoryId}/node_histories/`,
        { params }
      )
    },
    getNodeResult(nodeHistoryId) {
      return client.get(`automation/node_histories/${nodeHistoryId}/result/`)
    },
  }
}
