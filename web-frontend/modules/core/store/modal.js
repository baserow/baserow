let escHandler = null

export const state = () => ({
  modalStack: [],
})

export const mutations = {
  PUSH_MODAL(state, modal) {
    state.modalStack.push(modal)
  },
  POP_MODAL(state, modalId) {
    state.modalStack = state.modalStack.filter((m) => m.id !== modalId)
  },
}

export const actions = {
  pushModal({ commit, state, dispatch }, modal) {
    commit('PUSH_MODAL', modal)

    if (state.modalStack.length === 1) {
      dispatch('addEscListener')
    }
  },

  popModal({ commit, state, dispatch }, modalId) {
    commit('POP_MODAL', modalId)

    if (state.modalStack.length === 0) {
      dispatch('removeEscListener')
    }
  },

  addEscListener({ dispatch }) {
    if (!escHandler) {
      escHandler = (event) => {
        if (event.key === 'Escape') {
          dispatch('closeTopmostModal')
        }
      }
      window.addEventListener('keyup', escHandler)
    }
  },

  removeEscListener() {
    if (escHandler) {
      window.removeEventListener('keyup', escHandler)
      escHandler = null
    }
  },

  closeTopmostModal({ state }) {
    if (state.modalStack.length > 0) {
      const topmostModal = state.modalStack[state.modalStack.length - 1]
      if (topmostModal.canClose) {
        this.$bus.$emit(`modal:close:${topmostModal.id}`)
      }
    }
  },
}

export const getters = {}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
