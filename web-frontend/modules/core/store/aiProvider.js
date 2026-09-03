import aiProviderService from '@baserow/modules/core/services/aiProvider'

export const state = () => ({
  providers: [],
  providerTypes: [],
  featureSettings: [],
  workspaceId: null,
  loading: false,
  loaded: false,
  requestGeneration: 0,
  providersRevision: 0,
  featureSettingsRevision: 0,
})

export const mutations = {
  SET_PROVIDERS(state, providers) {
    state.providers = providers
  },
  SET_PROVIDER_TYPES(state, providerTypes) {
    state.providerTypes = providerTypes
  },
  SET_FEATURE_SETTINGS(state, featureSettings) {
    state.featureSettings = featureSettings
  },
  SET_WORKSPACE_ID(state, workspaceId) {
    state.workspaceId = workspaceId
  },
  SET_LOADING(state, loading) {
    state.loading = loading
  },
  SET_LOADED(state, loaded) {
    state.loaded = loaded
  },
  SET_REQUEST_GENERATION(state, generation) {
    state.requestGeneration = generation
  },
  BUMP_PROVIDERS_REVISION(state) {
    state.providersRevision += 1
  },
  BUMP_FEATURE_SETTINGS_REVISION(state) {
    state.featureSettingsRevision += 1
  },
  ADD_PROVIDER(state, provider) {
    const index = state.providers.findIndex((item) => item.id === provider.id)
    if (index === -1) {
      state.providers.push(provider)
    } else {
      state.providers.splice(index, 1, provider)
    }
  },
  UPDATE_PROVIDER(state, provider) {
    const index = state.providers.findIndex((item) => item.id === provider.id)
    if (index !== -1) state.providers.splice(index, 1, provider)
  },
  DELETE_PROVIDER(state, providerId) {
    state.providers = state.providers.filter((item) => item.id !== providerId)
  },
  ADD_MODEL(state, { providerId, model }) {
    const provider = state.providers.find((item) => item.id === providerId)
    if (provider) {
      const index = provider.models.findIndex((item) => item.id === model.id)
      if (index === -1) {
        provider.models.push(model)
      } else {
        provider.models.splice(index, 1, model)
      }
    }
  },
  UPDATE_MODEL(state, model) {
    for (const provider of state.providers) {
      const index = provider.models.findIndex((item) => item.id === model.id)
      if (index !== -1) {
        provider.models.splice(index, 1, model)
        return
      }
    }
  },
  UPDATE_MODEL_TEST_RESULTS(state, results) {
    const resultsById = new Map(
      results.map((result) => [result.model_id, result])
    )
    for (const provider of state.providers) {
      for (const model of provider.models) {
        const result = resultsById.get(model.id)
        if (result) {
          model.last_test_at = result.tested_at
          model.last_test_status = result.status
          model.last_test_error = result.error
          model.last_test_feature_results = result.feature_results
        }
      }
    }
  },
  DELETE_MODEL(state, modelId) {
    for (const provider of state.providers) {
      provider.models = provider.models.filter((item) => item.id !== modelId)
    }
  },
  UPDATE_FEATURE_SETTING(state, featureSetting) {
    const index = state.featureSettings.findIndex(
      (setting) => setting.feature_type === featureSetting.feature_type
    )
    if (index === -1) state.featureSettings.push(featureSetting)
    else state.featureSettings.splice(index, 1, featureSetting)
  },
}

const commitIfScopeIsCurrent = (
  state,
  workspaceId,
  commit,
  mutation,
  payload,
  revisionMutation = null
) => {
  if (state.workspaceId === workspaceId) {
    if (revisionMutation !== null) {
      commit(revisionMutation)
    }
    commit(mutation, payload)
  }
}

export const actions = {
  async fetchInitial(
    { commit, state },
    { workspaceId = null, realtimeRecovery = false } = {}
  ) {
    // Claim the scope before awaiting; a refresh must not reload the old one.
    if (state.workspaceId !== workspaceId) {
      commit('SET_WORKSPACE_ID', workspaceId)
      commit('SET_PROVIDERS', [])
      commit('SET_PROVIDER_TYPES', [])
      commit('SET_FEATURE_SETTINGS', [])
      commit('SET_LOADED', false)
    }
    const requestGeneration = state.requestGeneration + 1
    commit('SET_REQUEST_GENERATION', requestGeneration)
    const providersRevision = state.providersRevision
    const featureSettingsRevision = state.featureSettingsRevision
    commit('SET_LOADING', true)
    try {
      const service = aiProviderService(this.$client, workspaceId)
      const [providers, providerTypes, featureSettings] = await Promise.all([
        service.fetchAll(realtimeRecovery),
        service.fetchTypes(),
        service.fetchFeatureSettings(realtimeRecovery),
      ])
      // A newer scope may have been claimed while this request was in flight.
      if (
        state.workspaceId !== workspaceId ||
        state.requestGeneration !== requestGeneration
      ) {
        return
      }
      if (state.providersRevision === providersRevision) {
        commit('SET_PROVIDERS', providers.data)
      }
      if (state.featureSettingsRevision === featureSettingsRevision) {
        commit('SET_FEATURE_SETTINGS', featureSettings.data)
      }
      commit('SET_PROVIDER_TYPES', providerTypes.data)
      commit('SET_LOADED', true)
    } finally {
      if (
        state.workspaceId === workspaceId &&
        state.requestGeneration === requestGeneration
      ) {
        commit('SET_LOADING', false)
      }
    }
  },
  async refresh({ commit, state }) {
    if (!state.loaded) {
      return []
    }
    const workspaceId = state.workspaceId
    const requestGeneration = state.requestGeneration + 1
    commit('SET_REQUEST_GENERATION', requestGeneration)
    const providersRevision = state.providersRevision
    const featureSettingsRevision = state.featureSettingsRevision
    const service = aiProviderService(this.$client, workspaceId)
    const [providers, featureSettings] = await Promise.all([
      service.fetchAll(),
      service.fetchFeatureSettings(),
    ])
    if (
      state.workspaceId !== workspaceId ||
      state.requestGeneration !== requestGeneration
    ) {
      return []
    }
    const providersAreCurrent = state.providersRevision === providersRevision
    if (providersAreCurrent) {
      commit('SET_PROVIDERS', providers.data)
    }
    if (state.featureSettingsRevision === featureSettingsRevision) {
      commit('SET_FEATURE_SETTINGS', featureSettings.data)
    }
    return providersAreCurrent ? providers.data : []
  },
  replaceFromRealtime(
    { commit, state },
    { workspaceId, providers, featureSettings }
  ) {
    if (state.workspaceId === workspaceId) {
      if (providers !== undefined) {
        commit('BUMP_PROVIDERS_REVISION')
        commit('SET_PROVIDERS', providers)
      }
      if (featureSettings !== undefined) {
        commit('BUMP_FEATURE_SETTINGS_REVISION')
        commit('SET_FEATURE_SETTINGS', featureSettings)
      }
    }
  },
  async create({ commit, state }, payload) {
    const workspaceId = payload.workspaceId ?? null
    const values = workspaceId === null ? payload : payload.values
    const { data } = await aiProviderService(this.$client, workspaceId).create(
      values
    )
    commitIfScopeIsCurrent(
      state,
      workspaceId,
      commit,
      'ADD_PROVIDER',
      data,
      'BUMP_PROVIDERS_REVISION'
    )
    return data
  },
  async update({ commit, state }, { providerId, values, workspaceId = null }) {
    const { data } = await aiProviderService(this.$client, workspaceId).update(
      providerId,
      values
    )
    commitIfScopeIsCurrent(
      state,
      workspaceId,
      commit,
      'UPDATE_PROVIDER',
      data,
      'BUMP_PROVIDERS_REVISION'
    )
    return data
  },
  async delete({ commit, state }, payload) {
    const providerId =
      typeof payload === 'object' ? payload.providerId : payload
    const workspaceId =
      typeof payload === 'object' ? (payload.workspaceId ?? null) : null
    await aiProviderService(this.$client, workspaceId).delete(providerId)
    commitIfScopeIsCurrent(
      state,
      workspaceId,
      commit,
      'DELETE_PROVIDER',
      providerId,
      'BUMP_PROVIDERS_REVISION'
    )
  },
  async createModel(
    { commit, state },
    { providerId, values, workspaceId = null }
  ) {
    const { data } = await aiProviderService(
      this.$client,
      workspaceId
    ).createModel(providerId, values)
    commitIfScopeIsCurrent(
      state,
      workspaceId,
      commit,
      'ADD_MODEL',
      {
        providerId,
        model: data,
      },
      'BUMP_PROVIDERS_REVISION'
    )
    return data
  },
  async discoverModels(_context, payload) {
    const providerType =
      typeof payload === 'object' ? payload.providerType : payload
    const workspaceId =
      typeof payload === 'object' ? (payload.workspaceId ?? null) : null
    const { data } = await aiProviderService(
      this.$client,
      workspaceId
    ).discoverModels(providerType)
    return data
  },
  async updateModel(
    { commit, state },
    { modelId, values, workspaceId = null }
  ) {
    const { data } = await aiProviderService(
      this.$client,
      workspaceId
    ).updateModel(modelId, values)
    commitIfScopeIsCurrent(
      state,
      workspaceId,
      commit,
      'UPDATE_MODEL',
      data,
      'BUMP_PROVIDERS_REVISION'
    )
    return data
  },
  async deleteModel({ commit, state }, payload) {
    const modelId = typeof payload === 'object' ? payload.modelId : payload
    const workspaceId =
      typeof payload === 'object' ? (payload.workspaceId ?? null) : null
    await aiProviderService(this.$client, workspaceId).deleteModel(modelId)
    commitIfScopeIsCurrent(
      state,
      workspaceId,
      commit,
      'DELETE_MODEL',
      modelId,
      'BUMP_PROVIDERS_REVISION'
    )
  },
  async testModels({ commit, state }, payload) {
    const workspaceId = payload.workspaceId ?? null
    const values = workspaceId === null ? payload : payload.values
    const { data } = await aiProviderService(
      this.$client,
      workspaceId
    ).testModels(values)
    commitIfScopeIsCurrent(
      state,
      workspaceId,
      commit,
      'UPDATE_MODEL_TEST_RESULTS',
      data.results,
      'BUMP_PROVIDERS_REVISION'
    )
    return data.results
  },
  async updateFeatureSetting(
    { commit, dispatch, state },
    { featureType, values, workspaceId = null }
  ) {
    const { data } = await aiProviderService(
      this.$client,
      workspaceId
    ).updateFeatureSetting(featureType, values)
    commitIfScopeIsCurrent(
      state,
      workspaceId,
      commit,
      'UPDATE_FEATURE_SETTING',
      data,
      'BUMP_FEATURE_SETTINGS_REVISION'
    )
    // The setting response describes the raw selection, while workspace
    // availability also accounts for inheritance and legacy fallbacks. Refresh
    // that authoritative view immediately; realtime remains the cross-tab path.
    try {
      await dispatch('workspace/refreshAllGenerativeAIModels', null, {
        root: true,
      })
    } catch {
      // Saving succeeded, so don't report a false failure if this optional
      // synchronization request is interrupted. Realtime can still reconcile it.
    }
    return data
  },
}

export const getters = {
  // One scope at a time: reads name the scope they expect.
  getAll: (state) => (workspaceId) =>
    state.workspaceId === workspaceId ? state.providers : [],
  getTypes: (state) => (workspaceId) =>
    state.workspaceId === workspaceId ? state.providerTypes : [],
  getFeatureSettings: (state) => (workspaceId) =>
    state.workspaceId === workspaceId ? state.featureSettings : [],
  isLoading: (state) => state.loading,
  hasLoaded: (state) => state.loaded,
  getWorkspaceId: (state) => state.workspaceId,
  isLoaded: (state) => (workspaceId) =>
    state.loaded && state.workspaceId === workspaceId,
}

export default { namespaced: true, state, mutations, actions, getters }
