import TemplatesAdminService from '@baserow/modules/core/services/admin/templates'

// The request in flight per store, kept out of the state so that it never enters
// the serialized payload.
const pendingRequests = new WeakMap()

export const state = () => ({
  counts: null,
})

export const mutations = {
  SET_COUNTS(state, counts) {
    state.counts = counts
  },
  RESET(state) {
    state.counts = null
  },
}

export const actions = {
  fetchCounts({ commit }, { force = false } = {}) {
    const pending = pendingRequests.get(this)
    if (pending && !force) {
      return pending
    }
    const request = TemplatesAdminService(this.$client)
      .counts()
      .then(({ data }) => {
        if (pendingRequests.get(this) === request) {
          commit('SET_COUNTS', data)
        }
      })
      .finally(() => {
        if (pendingRequests.get(this) === request) {
          pendingRequests.delete(this)
        }
      })
    pendingRequests.set(this, request)
    return request
  },
  async ensureCounts({ state, dispatch }) {
    if (state.counts !== null || pendingRequests.has(this)) {
      return
    }
    try {
      await dispatch('fetchCounts')
    } catch {
      // The badge stays hidden: the admin didn't ask for the counts.
    }
  },
  reset({ commit }) {
    pendingRequests.delete(this)
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
