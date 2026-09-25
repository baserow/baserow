export default (client) => {
  return {
    fetchItems({ workspaceIds = [], types = [], limit, cursor = null }) {
      const params = { limit }
      if (cursor !== null) {
        params.cursor = cursor
      }
      if (workspaceIds.length > 0) {
        params.workspace_ids = workspaceIds.join(',')
      }
      if (types.length > 0) {
        params.types = types.join(',')
      }
      return client.get('/last-viewed/items/', { params })
    },
  }
}
