export default (client) => {
  const base = (agentId) => `/agent-permissions/${agentId}/`
  return {
    get(agentId) {
      return client.get(base(agentId))
    },
    fetchSubjectOptions(agentId, params) {
      return client.get(base(agentId) + 'options/', { params })
    },
    update(agentId, capability, { role, subjects }) {
      return client.put(base(agentId) + capability + '/', { role, subjects })
    },
  }
}
