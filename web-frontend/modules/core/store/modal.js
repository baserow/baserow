export const state = () => ({
  lastModalId: 0,
  modalsStack: [],
})

export const mutations = {
  SET_LAST_MODAL_ID(state, lastModalId) {
    state.lastModalId = lastModalId
  },
  PUSH_TO_STACK(state, modalId) {
    state.modalsStack.push(modalId)
  },
  REMOVE_FROM_STACK(state, modalId) {
    const index = state.modalsStack.indexOf(modalId)
    if (index !== -1) {
      state.modalsStack.splice(index, 1)
    }
  },
}

export const actions = {
  getNewModalId({ commit }) {
    const newModalId = state.lastModalId + 1
    commit('SET_LAST_MODAL_ID', newModalId)
    return newModalId
  },
  pushModal({ commit }, modalId) {
    commit('PUSH_TO_STACK', modalId)
  },
  removeModal({ commit }, modalId) {
    commit('REMOVE_FROM_STACK', modalId)
  },
}

export const getters = {
  topMostModalId(state) {
    return state.modalsStack.length
      ? state.modalsStack[state.modalsStack - 1]
      : null
  },
  modalsStack(state) {
    return state.modalsStack
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
