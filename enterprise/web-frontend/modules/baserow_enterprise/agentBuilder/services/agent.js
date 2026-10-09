export default (client) => ({
  fetchAll(agentBuilderId) {
    return client.get(`/agent-builder/${agentBuilderId}/agents/`)
  },
  create(agentBuilderId, name) {
    return client.post(`/agent-builder/${agentBuilderId}/agents/`, { name })
  },
  read(agentId) {
    return client.get(`/agent-builder/agents/${agentId}/`)
  },
  update(agentId, values) {
    return client.patch(`/agent-builder/agents/${agentId}/`, values)
  },
  delete(agentId) {
    return client.delete(`/agent-builder/agents/${agentId}/`)
  },
})
