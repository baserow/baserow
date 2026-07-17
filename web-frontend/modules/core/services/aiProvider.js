export default (client) => ({
  fetchAll() {
    return client.get('/ai-providers/')
  },
  fetchTypes() {
    return client.get('/ai-providers/types/')
  },
  create(values) {
    return client.post('/ai-providers/', values)
  },
  update(providerId, values) {
    return client.patch(`/ai-providers/${providerId}/`, values)
  },
  delete(providerId) {
    return client.delete(`/ai-providers/${providerId}/`)
  },
  createModel(providerId, values) {
    return client.post(`/ai-providers/${providerId}/models/`, values)
  },
  discoverModels(providerType) {
    return client.get('/ai-providers/models/discover/', {
      params: { provider_type: providerType },
    })
  },
  updateModel(modelId, values) {
    return client.patch(`/ai-providers/models/${modelId}/`, values)
  },
  deleteModel(modelId) {
    return client.delete(`/ai-providers/models/${modelId}/`)
  },
  testModels(values) {
    return client.post('/ai-providers/models/test/', values)
  },
})
