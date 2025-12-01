export default (client) => {
  return {
    /**
     * Performs a workspace search across all searchable content types in a workspace.
     */
    search(workspaceId, params) {
      return client.get(`/search/workspace/${workspaceId}/`, { params })
    },
  }
}
