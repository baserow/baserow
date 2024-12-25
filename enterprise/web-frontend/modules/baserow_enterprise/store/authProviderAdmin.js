import authProviderAdmin from '@baserow_enterprise/services/authProviderAdmin'
import { notifyIf } from '@baserow/modules/core/utils/error'

function populateProviderType(authProviderType, registry) {
  const type = registry.get('authProvider', authProviderType.type)
  return type.populate(authProviderType)
}

export const state = () => ({
  items: {},
  nextProviderId: null,
})

export const mutations = {
  SET_ITEMS(state, items) {
    state.items = items
  },
  ADD_ITEM(state, item) {
    const authProviderType = item.type
    const authProviders = state.items[authProviderType]?.authProviders || []
    state.items[authProviderType] = {
      ...state.items[authProviderType],
      authProviders: [item, ...authProviders],
    }
  },
  DELETE_ITEM(state, item) {
    const authProviderType = item.type
    const authProviders = state.items[authProviderType]?.authProviders || []
    state.items[authProviderType] = {
      ...state.items[authProviderType],
      authProviders: authProviders.filter((p) => p.id !== item.id),
    }
  },
  UPDATE_ITEM(state, item) {
    const authProviderType = item.type
    const originalItemType = state.items[authProviderType]
    const authProviders = originalItemType?.authProviders || []
    state.items[authProviderType] = {
      ...originalItemType,
      authProviders: authProviders.map((p) => (p.id === item.id ? item : p)),
    }
  },
  SET_NEXT_PROVIDER_ID(state, providerId) {
    state.nextProviderId = providerId
  },
}

export const actions = {
  async fetchAll({ commit }) {
    const { data } = await authProviderAdmin(this.$client).fetchAll()
    const items = {}
    for (const authProviderType of data.auth_provider_types) {
      items[authProviderType.type] = populateProviderType(
        authProviderType,
        this.$registry
      )
    }
    commit('SET_ITEMS', items)
    return items
  },
  async create({ commit, dispatch }, { type, values }) {
    const { data: item } = await authProviderAdmin(this.$client).create({
      type,
      ...values,
    })
    commit('ADD_ITEM', item)
    await dispatch('fetchNextProviderId')
    return item
  },
  async update({ commit }, { authProvider, values }) {
    const { data: item } = await authProviderAdmin(this.$client).update(
      authProvider.id,
      values
    )
    commit('UPDATE_ITEM', item)
    return item
  },
  async delete({ commit }, item) {
    try {
      await authProviderAdmin(this.$client).delete(item.id)
      commit('DELETE_ITEM', item)
    } catch (error) {
      notifyIf(error, 'authProvider')
    }
  },
  async fetchNextProviderId({ commit }) {
    const { data } = await authProviderAdmin(this.$client).fetchNextProviderId()
    const providerId = data.next_provider_id
    commit('SET_NEXT_PROVIDER_ID', providerId)
    return providerId
  },
  async setEnabled({ commit, dispatch }, { authProvider, enabled }) {
    // use optimistic update to enable/disable the auth provider
    const wasEnabled = authProvider.enabled
    commit('UPDATE_ITEM', { ...authProvider, enabled })
    try {
      await authProviderAdmin(this.$client).update(authProvider.id, { enabled })
    } catch (error) {
      commit('UPDATE_ITEM', { ...authProvider, enabled: wasEnabled })
      notifyIf(error, 'authProvider')
    }
  },
}

export const getters = {
  getAll: (state) => {
    return state.items
  },
  getAllOrdered: (state) => {
    const authProviders = []
    const authProviderTypesOrdered = Object.values(state.items).sort(
      (typeA, typeB) => typeA.order - typeB.order
    )
    for (const authProviderType of authProviderTypesOrdered) {
      if (authProviderType.hasAdminSettings) {
        authProviders.push(...authProviderType.authProviders)
      }
    }
    return authProviders
  },
  getNextProviderId: (state) => {
    return state.nextProviderId
  },
  getType: (state) => (type) => {
    return state.items[type]
  },
  isOneProviderEnabled: (state) => {
    let nEnabled = 0
    for (const authProviderType of Object.values(state.items)) {
      for (const authProvider of authProviderType.authProviders) {
        if (authProvider.enabled) {
          nEnabled += 1
        }
      }
    }
    return nEnabled === 1
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
