import { fetchPublicBuilder } from '@baserow/modules/builder/services/publishedBuilder'

const state = () => ({
  pageMode: 'public',
  // The domain name the published builder was loaded from. Stays `null` when
  // it was loaded by id, for example in preview mode.
  publicDomain: null,
})

const mutations = {
  SET_PAGE_MODE(state, mode) {
    state.pageMode = mode
  },
  SET_PUBLIC_DOMAIN(state, domain) {
    state.publicDomain = domain
  },
}

const actions = {
  setPageMode({ commit }, mode) {
    commit('SET_PAGE_MODE', mode)
  },
  async fetch({ commit, dispatch }, params) {
    const data = await fetchPublicBuilder(this.$client, params)
    const { mode = 'public', builderId = null, domain = null } = params
    commit(
      'SET_PUBLIC_DOMAIN',
      mode === 'public' && builderId === null ? domain : null
    )

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
  getPublicDomain: (state) => state.publicDomain,
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
