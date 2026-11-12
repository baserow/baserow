export default (client) => ({
  list(agentId) {
    return client.get(`/agent/${agentId}/actions/`)
  },
  create(agentId, values) {
    return client.post(`/agent/${agentId}/actions/`, values)
  },
  update(agentId, actionId, values) {
    return client.patch(`/agent/${agentId}/actions/${actionId}/`, values)
  },
  delete(agentId, actionId) {
    return client.delete(`/agent/${agentId}/actions/${actionId}/`)
  },
})
