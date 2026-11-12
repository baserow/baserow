export default (client) => ({
  list(agentId) {
    return client.get(`/agent/${agentId}/triggers/`)
  },
  listTypes(agentId) {
    return client.get(`/agent/${agentId}/trigger-types/`)
  },
  create(agentId, values) {
    return client.post(`/agent/${agentId}/triggers/`, values)
  },
  update(agentId, triggerId, values) {
    return client.patch(`/agent/${agentId}/triggers/${triggerId}/`, values)
  },
  delete(agentId, triggerId) {
    return client.delete(`/agent/${agentId}/triggers/${triggerId}/`)
  },
})
