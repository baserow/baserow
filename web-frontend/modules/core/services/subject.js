export default (client) => ({
  list(workspaceId) {
    return client.get('/subjects/', {
      params: {
        workspace_id: workspaceId,
        subject_types: 'auth.User,core.Agent',
        size: 100,
      },
    })
  },
})
