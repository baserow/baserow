export default (client) => {
  return {
    fetchAll() {
      return client.get('/mcp/endpoints/')
    },
    create(values) {
      return client.post('/mcp/endpoints/', values)
    },
    update(endpointId, values) {
      return client.patch(`/mcp/endpoint/${endpointId}/`, values)
    },
    delete(endpointId) {
      return client.delete(`/mcp/endpoint/${endpointId}/`)
    },
  }
}
