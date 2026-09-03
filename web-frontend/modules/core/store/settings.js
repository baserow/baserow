import SettingsService from '@baserow/modules/core/services/settings'
import { clone } from '@baserow/modules/core/utils/object'

export const state = () => ({
  loaded: false,
  settings: {},
  aiFeatureRevisions: {},
  requestGeneration: 0,
})

export const mutations = {
  SET_SETTINGS(state, values) {
    state.settings = values
  },
  UPDATE_SETTINGS(state, values) {
    state.settings = Object.assign({}, state.settings, values)
  },
  APPLY_REALTIME_AI_FEATURES(state, values) {
    for (const featureType of Object.keys(values)) {
      state.aiFeatureRevisions[featureType] =
        (state.aiFeatureRevisions[featureType] || 0) + 1
    }
    state.settings = Object.assign({}, state.settings, values)
  },
  SET_LOADED(state, value) {
    state.loaded = value
  },
  SET_REQUEST_GENERATION(state, value) {
    state.requestGeneration = value
  },
  HIDE_ADMIN_SIGNUP_PAGE(state) {
    state.settings.show_admin_signup_page = false
  },
}

export const actions = {
  async load({ commit, state }, { realtimeRecovery = false } = {}) {
    const { $client } = this
    const requestGeneration = state.requestGeneration + 1
    commit('SET_REQUEST_GENERATION', requestGeneration)
    const requestRevisions = { ...state.aiFeatureRevisions }
    const { data } = await SettingsService($client).get(realtimeRecovery)
    if (state.requestGeneration !== requestGeneration) {
      return
    }
    const newerAISettings = Object.fromEntries(
      Object.keys(state.aiFeatureRevisions)
        .filter(
          (featureType) =>
            state.aiFeatureRevisions[featureType] !==
            requestRevisions[featureType]
        )
        .map((featureType) => [featureType, state.settings[featureType]])
    )
    commit('SET_SETTINGS', { ...data, ...newerAISettings })
    commit('SET_LOADED', true)
  },
  async update({ commit, getters }, values) {
    const { $client } = this
    const oldValues = clone(getters.get)
    commit('UPDATE_SETTINGS', values)

    try {
      await SettingsService($client).update(values)
    } catch (e) {
      commit('SET_SETTINGS', oldValues)
      throw e
    }
  },
  forceUpdateAIFeatures({ commit }, aiFeatures) {
    commit('APPLY_REALTIME_AI_FEATURES', aiFeatures)
  },
  hideAdminSignupPage({ commit }) {
    commit('HIDE_ADMIN_SIGNUP_PAGE')
  },
}

export const getters = {
  isLoaded(state) {
    return state.loaded
  },
  get(state) {
    return state.settings
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
