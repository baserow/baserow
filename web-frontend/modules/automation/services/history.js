export const WORKFLOW_HISTORY_PAGE_SIZE = 20

export default (client) => {
  return {
    getWorkflowHistory(workflowId, page = 1) {
      return client.get(`automation/workflows/${workflowId}/history/`, {
        params: { page, size: WORKFLOW_HISTORY_PAGE_SIZE },
      })
    },
    getNodeHistories(workflowHistoryId) {
      return client.get(
        `automation/workflow_histories/${workflowHistoryId}/node_histories/`
      )
    },
    getNodeResult(nodeHistoryId) {
      return client.get(`automation/node_histories/${nodeHistoryId}/result/`)
    },
    cancelWorkflowHistory(workflowHistoryId) {
      return client.post(
        `automation/workflow_histories/${workflowHistoryId}/cancel/`
      )
    },
  }
}
