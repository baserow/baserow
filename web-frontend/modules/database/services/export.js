export default (client) => {
  return {
    export(tableId, values) {
      return client.post(`/database/export/table/${tableId}/`, {
        ...values,
      })
    },
    exportWorkspace(workspaceId, values) {
      return client.post(
        `/database/export/workspace/${workspaceId}/async/`,
        values
      )
    },
    get(jobId) {
      return client.get(`/database/export/${jobId}/`)
    },
  }
}
