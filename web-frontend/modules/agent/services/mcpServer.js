/** Tool review endpoints of MCP server integrations. */
export default (client) => ({
  refreshTools(integrationId) {
    return client.post(`/integrations/mcp/${integrationId}/refresh-tools/`)
  },
  updateTools(integrationId, tools) {
    return client.patch(`/integrations/mcp/${integrationId}/tools/`, { tools })
  },
})
