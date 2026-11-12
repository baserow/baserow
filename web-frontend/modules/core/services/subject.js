export default (client) => ({
  list(
    workspaceId,
    {
      page = 1,
      search = '',
      subjectTypes = 'auth.User',
      userType = 'human',
      size = 100,
    } = {}
  ) {
    return client.get('/subjects/', {
      params: {
        workspace_id: workspaceId,
        page,
        search,
        subject_types: subjectTypes,
        user_type: userType,
        size,
      },
    })
  },
})
