import { uuid } from '@baserow/modules/core/utils/string'

export const state = () => ({
  items: [],
})

export const mutations = {
  ADD(state, toast) {
    state.items.unshift(toast)
  },
  REMOVE(state, toast) {
    const index = state.items.indexOf(toast)
    state.items.splice(index, 1)
  },
}

export const actions = {
  /**
   * Shows a toast message to the user.
   */
  add({ commit }, { type, title = null, message = null, ...rest }) {
    commit('ADD', {
      id: uuid(),
      type,
      title,
      message,
      ...rest,
    })
  },
  infoNeutral({ dispatch }, { title, message }) {
    dispatch('add', { type: 'info-neutral', title, message })
  },
  info({ dispatch }, { title, message }) {
    dispatch('add', { type: 'info-primary', title, message })
  },
  error({ dispatch }, { title, message, details }) {
    dispatch('add', { type: 'error', title, message, details })
  },
  warning({ dispatch }, { title, message, details }) {
    dispatch('add', { type: 'warning', title, message, details })
  },
  success({ dispatch }, { title, message }) {
    dispatch('add', { type: 'success', title, message })
  },
  remove({ commit }, toast) {
    commit('REMOVE', toast)
  },
}

export const getters = {
  all(state) {
    return state.items
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
