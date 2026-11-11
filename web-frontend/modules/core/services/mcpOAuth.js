export default (client) => {
  return {
    getConsent(query) {
      return client.get('/mcp/oauth/consent/', { params: { query } })
    },
    submitConsent(values) {
      return client.post('/mcp/oauth/consent/', values)
    },
    fetchConnections() {
      return client.get('/mcp/oauth/connections/')
    },
    updateTools(connectionId, allowedTools) {
      return client.patch(`/mcp/oauth/connections/${connectionId}/`, {
        allowed_tools: allowedTools,
      })
    },
    disconnect(connectionId) {
      return client.delete(`/mcp/oauth/connections/${connectionId}/`)
    },
  }
}
