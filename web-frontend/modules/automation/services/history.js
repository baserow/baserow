export default (client) => {
  return {
    getWorkflowHistory(workflowId) {
      return client.get(`automation/workflows/${workflowId}/history/`)
    },
    getNodeHistories(workflowHistoryId) {
      return client.get(
        `automation/workflow_histories/${workflowHistoryId}/node_histories/`
      )
    },
    getNodeResult(nodeHistoryId) {
      return client.get(`automation/node_histories/${nodeHistoryId}/result/`)
    },
  }
}
