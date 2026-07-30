import aiProviderService from '@baserow/modules/core/services/aiProvider'

export const state = () => ({
  providers: [],
  providerTypes: [],
  loading: false,
  loaded: false,
})

export const mutations = {
  SET_PROVIDERS(state, providers) {
    state.providers = providers
  },
  SET_PROVIDER_TYPES(state, providerTypes) {
    state.providerTypes = providerTypes
  },
  SET_LOADING(state, loading) {
    state.loading = loading
  },
  SET_LOADED(state, loaded) {
    state.loaded = loaded
  },
  ADD_PROVIDER(state, provider) {
    state.providers.push(provider)
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
    if (provider) provider.models.push(model)
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
        }
      }
    }
  },
  DELETE_MODEL(state, modelId) {
    for (const provider of state.providers) {
      provider.models = provider.models.filter((item) => item.id !== modelId)
    }
  },
}

export const actions = {
  async fetchInitial({ commit }) {
    commit('SET_LOADING', true)
    try {
      const service = aiProviderService(this.$client)
      const [providers, providerTypes] = await Promise.all([
        service.fetchAll(),
        service.fetchTypes(),
      ])
      commit('SET_PROVIDERS', providers.data)
      commit('SET_PROVIDER_TYPES', providerTypes.data)
      commit('SET_LOADED', true)
    } finally {
      commit('SET_LOADING', false)
    }
  },
  async refresh({ commit }) {
    const { data } = await aiProviderService(this.$client).fetchAll()
    commit('SET_PROVIDERS', data)
    return data
  },
  async create({ commit }, values) {
    const { data } = await aiProviderService(this.$client).create(values)
    commit('ADD_PROVIDER', data)
    return data
  },
  async update({ commit }, { providerId, values }) {
    const { data } = await aiProviderService(this.$client).update(
      providerId,
      values
    )
    commit('UPDATE_PROVIDER', data)
    return data
  },
  async delete({ commit }, providerId) {
    await aiProviderService(this.$client).delete(providerId)
    commit('DELETE_PROVIDER', providerId)
  },
  async createModel({ commit }, { providerId, values }) {
    const { data } = await aiProviderService(this.$client).createModel(
      providerId,
      values
    )
    commit('ADD_MODEL', { providerId, model: data })
    return data
  },
  async discoverModels(_context, providerType) {
    const { data } = await aiProviderService(this.$client).discoverModels(
      providerType
    )
    return data
  },
  async updateModel({ commit }, { modelId, values }) {
    const { data } = await aiProviderService(this.$client).updateModel(
      modelId,
      values
    )
    commit('UPDATE_MODEL', data)
    return data
  },
  async deleteModel({ commit }, modelId) {
    await aiProviderService(this.$client).deleteModel(modelId)
    commit('DELETE_MODEL', modelId)
  },
  async testModels({ commit }, values) {
    const { data } = await aiProviderService(this.$client).testModels(values)
    commit('UPDATE_MODEL_TEST_RESULTS', data.results)
    return data.results
  },
}

export const getters = {
  getAll: (state) => state.providers,
  getTypes: (state) => state.providerTypes,
  isLoading: (state) => state.loading,
  isLoaded: (state) => state.loaded,
}

export default { namespaced: true, state, mutations, actions, getters }
