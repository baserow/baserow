export default (client) => ({
  getReadiness(agentId) {
    return client.get(`/agent/${agentId}/readiness/`)
  },
  getConfiguration(agentId) {
    return client.get(`/agent/${agentId}/configuration/`)
  },
  updateConfiguration(agentId, values) {
    return client.patch(`/agent/${agentId}/configuration/`, values)
  },
})
