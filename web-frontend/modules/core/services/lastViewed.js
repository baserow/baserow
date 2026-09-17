export default (client) => {
  return {
    fetchItems({ workspaceIds = [], types = [], limit, offset = 0 }) {
      const params = { limit, offset }
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
