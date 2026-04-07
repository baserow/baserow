import { getToken, setToken } from '@baserow/modules/core/utils/auth'

export const state = () => ({
  authToken: null,
  isPublic: false,
})

export const mutations = {
  SET_AUTH_TOKEN(state, value) {
    state.authToken = value
  },
  SET_IS_PUBLIC(state, value) {
    state.isPublic = value
  },
}

export const actions = {
  async setAuthTokenFromCookiesIfNotSet({ state, commit }, { slug }) {
    if (!state.authToken) {
      const nuxtApp = this.app
      const token = await getToken(nuxtApp, slug)
      commit('SET_AUTH_TOKEN', token)
      return token
    } else {
      return state.authToken
    }
  },
  async setAuthToken({ commit }, { slug, token }) {
    const nuxtApp = this.app
    await setToken(nuxtApp, token, slug)
    commit('SET_AUTH_TOKEN', token)
  },
  setIsPublic({ commit }, value) {
    commit('SET_IS_PUBLIC', value)
  },
}

export const getters = {
  getAuthToken(state) {
    return state.authToken
  },
  getIsPublic(state) {
    return state.isPublic
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
