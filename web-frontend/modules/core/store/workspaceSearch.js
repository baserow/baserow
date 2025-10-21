import WorkspaceSearchService from '@baserow/modules/core/services/workspaceSearch'

export const state = () => ({
  searchTerm: '',
  results: [],
  loading: false,
})

export const mutations = {
  SET_SEARCH_TERM(state, term) {
    state.searchTerm = term
  },

  SET_RESULTS(state, results) {
    state.results = results
  },

  SET_LOADING(state, loading) {
    state.loading = loading
  },

  CLEAR_RESULTS(state) {
    state.results = []
  },
}

export const actions = {
  async search(
    { commit, state },
    {
      workspaceId,
      searchTerm,
      types = null,
      limit = 20,
      offset = 0,
      append = false,
    }
  ) {
    commit('SET_LOADING', true)
    commit('SET_SEARCH_TERM', searchTerm)

    try {
      const params = {
        query: searchTerm,
        limit,
        offset,
      }

      if (types && types.length > 0) {
        params.types = types
      }

      const { data } = await WorkspaceSearchService(this.$client).search(
        workspaceId,
        params
      )

      if (append) {
        const existing = Array.isArray(state.results) ? state.results : []
        const incoming = Array.isArray(data.results) ? data.results : []
        commit('SET_RESULTS', existing.concat(incoming))
      } else {
        commit('SET_RESULTS', Array.isArray(data.results) ? data.results : [])
      }

      return data
    } catch (error) {
      commit('SET_RESULTS', [])
      throw error
    } finally {
      commit('SET_LOADING', false)
    }
  },

  clearSearch({ commit }) {
    commit('SET_SEARCH_TERM', '')
    commit('CLEAR_RESULTS')
  },
}

export const getters = {
  hasResults: (state) =>
    Array.isArray(state.results) && state.results.length > 0,

  totalResultCount: (state) => {
    return Array.isArray(state.results) ? state.results.length : 0
  },

  isLoading: (state) => state.loading,

  getResultsByType: (state) => (type) => {
    if (!Array.isArray(state.results)) return []
    return state.results.filter((r) => r.type === type)
  },

  getAllResults: (state) => {
    return Array.isArray(state.results) ? state.results : []
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
