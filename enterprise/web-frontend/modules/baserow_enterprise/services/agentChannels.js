export default (client) => ({
  list(agentId) {
    return client.get(`/agent/${agentId}/channels/`)
  },
  create(agentId, values) {
    return client.post(`/agent/${agentId}/channels/`, values)
  },
  update(agentId, channelId, values) {
    return client.patch(`/agent/${agentId}/channels/${channelId}/`, values)
  },
  delete(agentId, channelId) {
    return client.delete(`/agent/${agentId}/channels/${channelId}/`)
  },
})
