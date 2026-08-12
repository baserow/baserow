export const state = () => ({
  // Indicates whether the user manually started the guided tour, ignoring the
  // completed state of the tours. Nothing is saved to the backend when a forced
  // tour finishes, and the user can stop it at any time.
  forced: false,
})

export const mutations = {
  SET_FORCED(state, forced) {
    state.forced = forced
  },
}

export const actions = {
  forceStart({ commit }) {
    commit('SET_FORCED', true)
  },
  stop({ commit }) {
    commit('SET_FORCED', false)
  },
}

export const getters = {
  isForced(state) {
    return state.forced
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
