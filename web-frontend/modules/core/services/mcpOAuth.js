export default (client) => {
  return {
    getConsent(query) {
      return client.get('/mcp/oauth/consent/', { params: { query } })
    },
    submitConsent(values) {
      return client.post('/mcp/oauth/consent/', values)
    },
  }
}
