export default (client) => ({
  list(
    workspaceId,
    {
      page = 1,
      search = '',
      subjectTypes = 'auth.User',
      identityType = 'human',
      size = 100,
    } = {}
  ) {
    return client.get('/subjects/', {
      params: {
        workspace_id: workspaceId,
        page,
        search,
        subject_types: subjectTypes,
        identity_type: identityType,
        size,
      },
    })
  },
})
