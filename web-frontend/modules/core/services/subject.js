export default (client) => ({
  async listAll(workspaceId, options) {
    const subjects = []
    let page = 1
    let next
    do {
      const { data } = await this.list(workspaceId, { ...options, page })
      subjects.push(...data.results)
      next = data.next
      page++
    } while (next)
    return subjects
  },
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
