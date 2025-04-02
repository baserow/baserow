export default (client) => {
  return {
    fetchAll() {
      return client.get('/templates/')
    },
    fetch(slug) {
      return client.get(`/templates/${slug}/`)
    },
    install(workspaceId, templateId) {
      return client.post(`/templates/install/${workspaceId}/${templateId}/`)
    },
    asyncInstall(workspaceId, templateId) {
      return client.post(
        `/templates/install/${workspaceId}/${templateId}/async/`
      )
    },
  }
}
