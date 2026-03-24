export default (client) => {
  return {
    fetchAll(scope, scopeId) {
      const params = { scope }
      if (scopeId) params.scope_id = scopeId
      return client.get('/ai-providers/', { params })
    },
    fetch(id) {
      return client.get(`/ai-providers/${id}/`)
    },
    create(values, scope, scopeId) {
      const params = { scope }
      if (scopeId) params.scope_id = scopeId
      return client.post('/ai-providers/', values, { params })
    },
    update(id, values) {
      return client.patch(`/ai-providers/${id}/`, values)
    },
    delete(id) {
      return client.delete(`/ai-providers/${id}/`)
    },
    toggleOverride(id, isEnabled, scope, scopeId) {
      const params = { scope }
      if (scopeId) params.scope_id = scopeId
      return client.patch(
        `/ai-providers/${id}/override/`,
        { is_enabled: isEnabled },
        { params }
      )
    },
    testModel(modelId) {
      return client.post(`/ai-providers/models/${modelId}/test/`)
    },
    fetchAvailableModels(feature, scope, scopeId) {
      const params = { feature, scope }
      if (scopeId) params.scope_id = scopeId
      return client.get('/ai-providers/models/', { params })
    },
    fetchFeatureDefaults(scope, scopeId) {
      const params = { scope }
      if (scopeId) params.scope_id = scopeId
      return client.get('/ai-providers/feature-defaults/', { params })
    },
    setFeatureDefault(featureType, providerModelId, scope, scopeId) {
      const params = { scope }
      if (scopeId) params.scope_id = scopeId
      return client.patch(
        '/ai-providers/feature-defaults/',
        { feature_type: featureType, provider_model_id: providerModelId },
        { params }
      )
    },
  }
}
