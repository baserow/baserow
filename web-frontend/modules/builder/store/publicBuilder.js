import PublishedBuilderService from '@baserow/modules/builder/services/publishedBuilder'

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
  async fetchById({ dispatch }, { builderId }) {
    const { $client } = this
    const { data } = await PublishedBuilderService($client).fetchById(builderId)

    return await dispatch('application/forceCreate', data, { root: true })
  },

  async fetchPreview({ dispatch }, { builderId }) {
    const { $client } = this
    const { data } =
      await PublishedBuilderService($client).fetchPreview(builderId)

    return await dispatch('application/forceCreate', data, { root: true })
  },

  async fetchByDomain({ dispatch }, { domain }) {
    const { $client } = this
    const { data } =
      await PublishedBuilderService($client).fetchByDomain(domain)

    return await dispatch('application/forceCreate', data, { root: true })
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
