export default (client) => {
  return {
    fetchAll() {
      return client.get('/templates/')
    },
    fetchOwn({ offset = 0, limit = 20, search = '' } = {}) {
      const params = { view: 'flat', type: 'user', owned: true, offset, limit }
      if (search) {
        params.search = search
      }
      return client.get('/templates/', { params })
    },
    fetch(slug) {
      return client.get(`/templates/${slug}/`)
    },
    install(workspaceId, templateId) {
      return client.post(`/templates/install/${workspaceId}/${templateId}/`)
    },
    /**
     * Installs the template into the workspace. The `revisionId` is the one of
     * the template that was shown, so that the install is refused if the template
     * was updated since.
     */
    asyncInstall(
      workspaceId,
      templateId,
      { latest = false, revisionId = null } = {}
    ) {
      const params = latest ? { latest: true } : {}
      if (revisionId !== null) {
        params.revision_id = revisionId
      }
      return client.post(
        `/templates/install/${workspaceId}/${templateId}/async/`,
        null,
        { params }
      )
    },
    delete(slug) {
      return client.delete(`/templates/${slug}/`)
    },
  }
}
