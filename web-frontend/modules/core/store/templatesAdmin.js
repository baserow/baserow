import TemplatesAdminService from '@baserow/modules/core/services/admin/templates'

export const state = () => ({
  counts: null,
  pending: null,
})

export const mutations = {
  SET_COUNTS(state, counts) {
    state.counts = counts
  },
  SET_PENDING(state, pending) {
    state.pending = pending
  },
  RESET(state) {
    state.counts = null
    state.pending = null
  },
}

export const actions = {
  fetchCounts({ state, commit }, { force = false } = {}) {
    if (state.pending && !force) {
      return state.pending
    }
    const request = TemplatesAdminService(this.$client)
      .counts()
      .then(({ data }) => {
        if (state.pending === request) {
          commit('SET_COUNTS', data)
        }
      })
      .finally(() => {
        if (state.pending === request) {
          commit('SET_PENDING', null)
        }
      })
    commit('SET_PENDING', request)
    return request
  },
  async ensureCounts({ state, dispatch }) {
    if (state.counts !== null || state.pending) {
      return
    }
    try {
      await dispatch('fetchCounts')
    } catch {
      // The badge stays hidden: the admin didn't ask for the counts.
    }
  },
  reset({ commit }) {
    commit('RESET')
  },
}

export const getters = {
  counts(state) {
    return state.counts
  },
  inReviewCount(state) {
    return state.counts?.in_review || 0
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
