import { getRealtimeRecoveryRequestConfig } from '@baserow/modules/core/plugins/realtimeProtocol'

export default (client, workspaceId = null) => {
  const config = (realtimeRecovery = false) => ({
    ...(workspaceId === null ? {} : { params: { workspace_id: workspaceId } }),
    ...(realtimeRecovery ? getRealtimeRecoveryRequestConfig() : {}),
  })

  return {
    fetchAll(realtimeRecovery = false) {
      return client.get('/ai-providers/', config(realtimeRecovery))
    },
    fetchTypes() {
      return client.get('/ai-providers/types/', config())
    },
    fetchFeatureSettings(realtimeRecovery = false) {
      return client.get('/ai-providers/features/', config(realtimeRecovery))
    },
    updateFeatureSetting(featureType, values) {
      return client.put(
        `/ai-providers/features/${featureType}/`,
        values,
        config()
      )
    },
    create(values) {
      return client.post('/ai-providers/', values, config())
    },
    update(providerId, values) {
      return client.patch(`/ai-providers/${providerId}/`, values, config())
    },
    delete(providerId) {
      return client.delete(`/ai-providers/${providerId}/`, config())
    },
    createModel(providerId, values) {
      return client.post(
        `/ai-providers/${providerId}/models/`,
        values,
        config()
      )
    },
    discoverModels(providerType) {
      return client.get('/ai-providers/models/discover/', {
        params: {
          provider_type: providerType,
          ...(workspaceId === null ? {} : { workspace_id: workspaceId }),
        },
      })
    },
    updateModel(modelId, values) {
      return client.patch(`/ai-providers/models/${modelId}/`, values, config())
    },
    deleteModel(modelId) {
      return client.delete(`/ai-providers/models/${modelId}/`, config())
    },
    testModels(values) {
      return client.post('/ai-providers/models/test/', values, config())
    },
  }
}
