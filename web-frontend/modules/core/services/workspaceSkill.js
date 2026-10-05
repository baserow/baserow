export default (client) => {
  return {
    list(workspaceId) {
      return client.get(`/skills/workspace/${workspaceId}/`)
    },
    create(workspaceId, values) {
      return client.post(`/skills/workspace/${workspaceId}/`, values)
    },
    update(skillId, values) {
      return client.patch(`/skills/${skillId}/`, values)
    },
    delete(skillId) {
      return client.delete(`/skills/${skillId}/`)
    },
  }
}
