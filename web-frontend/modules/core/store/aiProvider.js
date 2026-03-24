import aiProviderService from '@baserow/modules/core/services/aiProvider'

export const state = () => ({
  items: [],
  loaded: false,
  loading: false,
})

export const mutations = {
  SET_ITEMS(state, items) {
    state.items = items
    state.loaded = true
  },
  SET_LOADING(state, loading) {
    state.loading = loading
  },
  ADD_ITEM(state, item) {
    state.items.push(item)
  },
  UPDATE_ITEM(state, updatedItem) {
    const index = state.items.findIndex((i) => i.id === updatedItem.id)
    if (index !== -1) {
      state.items.splice(index, 1, updatedItem)
    }
  },
  DELETE_ITEM(state, itemId) {
    state.items = state.items.filter((i) => i.id !== itemId)
  },
}

export const actions = {
  async fetchAll({ commit }, { scope, scopeId }) {
    commit('SET_LOADING', true)
    try {
      const { data } = await aiProviderService(this.$client).fetchAll(
        scope,
        scopeId
      )
      commit('SET_ITEMS', data)
    } finally {
      commit('SET_LOADING', false)
    }
  },
  async create({ commit }, { values, scope, scopeId }) {
    const { data } = await aiProviderService(this.$client).create(
      values,
      scope,
      scopeId
    )
    commit('ADD_ITEM', data)
    return data
  },
  async update({ commit }, { id, values }) {
    const { data } = await aiProviderService(this.$client).update(id, values)
    commit('UPDATE_ITEM', data)
    return data
  },
  async delete({ commit }, { id }) {
    await aiProviderService(this.$client).delete(id)
    commit('DELETE_ITEM', id)
  },
  async toggleOverride({ commit, state }, { id, isEnabled, scope, scopeId }) {
    // Optimistic update
    const item = state.items.find((i) => i.id === id)
    if (item) {
      const prev = item.is_enabled
      commit('UPDATE_ITEM', { ...item, is_enabled: isEnabled })
      try {
        await aiProviderService(this.$client).toggleOverride(
          id,
          isEnabled,
          scope,
          scopeId
        )
      } catch (error) {
        commit('UPDATE_ITEM', { ...item, is_enabled: prev })
        throw error
      }
    }
  },
  async testModel({ commit, state }, { modelId }) {
    const { data } = await aiProviderService(this.$client).testModel(modelId)
    // Update the model in the corresponding provider
    for (const provider of state.items) {
      const modelIndex = provider.models.findIndex((m) => m.id === modelId)
      if (modelIndex !== -1) {
        const updatedModels = [...provider.models]
        updatedModels.splice(modelIndex, 1, data)
        commit('UPDATE_ITEM', { ...provider, models: updatedModels })
        break
      }
    }
    return data
  },
}

export const getters = {
  getAll(state) {
    return state.items
  },
  isLoading(state) {
    return state.loading
  },
  isLoaded(state) {
    return state.loaded
  },
  getInherited(state) {
    return state.items.filter((i) => !i.is_own_scope)
  },
  getOwn(state) {
    return state.items.filter((i) => i.is_own_scope)
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
