export default (client) => {
  return {
    getWorkflowHistory(workflowId) {
      return client.get(`automation/workflows/${workflowId}/history/`)
    },
  }
}
