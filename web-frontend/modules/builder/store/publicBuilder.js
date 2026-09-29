import { fetchPublicBuilder } from '@baserow/modules/builder/services/publishedBuilder'

const state = () => ({
  pageMode: 'public',
})

const mutations = {
  SET_PAGE_MODE(state, mode) {
    state.pageMode = mode
  },
}

const actions = {
  setPageMode({ commit }, mode) {
    commit('SET_PAGE_MODE', mode)
  },
  async fetch({ dispatch }, params) {
    const data = await fetchPublicBuilder(this.$client, params)

    return await dispatch('application/forceCreate', data, { root: true })
  },
  async fetchById({ dispatch }, { builderId }) {
    return await dispatch('fetch', { builderId })
  },

  async fetchPreview({ dispatch }, { builderId }) {
    return await dispatch('fetch', { mode: 'preview', builderId })
  },

  async fetchByDomain({ dispatch }, { domain }) {
    return await dispatch('fetch', { domain })
  },
}

const getters = {
  getPreviewBuilderId: (state, getters, rootState, rootGetters) =>
    state.pageMode === 'preview'
      ? rootGetters['application/getSelected']?.id
      : null,
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
