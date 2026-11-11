/** Tool review endpoints of MCP server integrations. */
export default (client) => ({
  refreshTools(integrationId) {
    return client.post(`/integrations/mcp/${integrationId}/refresh-tools/`)
  },
  startOAuth(integrationId) {
    return client.post(`/integrations/mcp/${integrationId}/oauth/start/`)
  },
  completeOAuth(state, code) {
    return client.post('/integrations/mcp/oauth/complete/', { state, code })
  },
  disconnectOAuth(integrationId) {
    return client.post(`/integrations/mcp/${integrationId}/oauth/disconnect/`)
  },
  updateTools(integrationId, tools) {
    return client.patch(`/integrations/mcp/${integrationId}/tools/`, { tools })
  },
})
