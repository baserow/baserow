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
    asyncInstall(workspaceId, templateId, { latest = false } = {}) {
      const params = latest ? { latest: true } : {}
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
