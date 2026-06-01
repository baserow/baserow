import { uuid } from '@baserow/modules/core/utils/string'
import { UNDO_REDO_STATES } from '@baserow/modules/core/utils/undoRedoConstants'

export const state = () => ({
  failedConnecting: false,
  reconnecting: false,
  authorizationError: false,
  userSessionExpired: false,
  userPasswordChanged: false,
  copying: false,
  pasting: false,
  clearing: false,
  // See UNDO_REDO_STATES for all possible values.
  undoRedoState: UNDO_REDO_STATES.HIDDEN,
  permissionsUpdated: false,
  workspaceOutdated: false,
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
  SET_FAILED_CONNECTING(state, value) {
    state.failedConnecting = value
  },
  SET_RECONNECTING(state, value) {
    state.reconnecting = !!value
  },
  SET_AUTHORIZATION_ERROR(state, value) {
    state.authorizationError = value
  },
  SET_COPYING(state, value) {
    state.copying = value
  },
  SET_PASTING(state, value) {
    state.pasting = value
  },
  SET_CLEARING(state, value) {
    state.clearing = value
  },
  SET_UNDO_REDO_STATE(state, value) {
    state.undoRedoState = value
  },
  SET_USER_SESSION_EXPIRED(state, value) {
    state.userSessionExpired = value
  },
  SET_PERMISSIONS_UPDATED(state, value) {
    state.permissionsUpdated = value
  },
  SET_USER_PASSWORD_CHANGED(state, value) {
    state.userPasswordChanged = value
  },
  SET_WORKSPACE_OUTDATED(state, value) {
    state.workspaceOutdated = value
  },
}

export const actions = {
  /**
   * Shows a toast message to the user.
   */
  add({ commit }, { type, title = null, message = null, data = null }) {
    commit('ADD', {
      id: uuid(),
      type,
      title,
      message,
      data,
    })
  },
  info({ dispatch }, { title, message }) {
    dispatch('add', { type: 'info-neutral', title, message })
  },
  error({ dispatch }, { title, message }) {
    dispatch('add', { type: 'error', title, message })
  },
  warning({ dispatch }, { title, message }) {
    dispatch('add', { type: 'warning', title, message })
  },
  success({ dispatch }, { title, message }) {
    dispatch('add', { type: 'success', title, message })
  },
  restore({ dispatch }, restoreData) {
    dispatch('add', {
      type: 'restore',
      data: restoreData,
    })
  },
  remove({ commit }, toast) {
    commit('REMOVE', toast)
  },
  setFailedConnecting({ commit }, value) {
    if (value) {
      commit('SET_RECONNECTING', false)
    }
    commit('SET_FAILED_CONNECTING', value)
  },
  setReconnecting({ commit }, value) {
    if (value) {
      commit('SET_FAILED_CONNECTING', false)
    }
    commit('SET_RECONNECTING', value)
  },
  setAuthorizationError({ commit }, value) {
    commit('SET_AUTHORIZATION_ERROR', value)
  },
  setCopying({ commit }, value) {
    commit('SET_COPYING', value)
  },
  setPasting({ commit }, value) {
    commit('SET_PASTING', value)
  },
  setClearing({ commit }, value) {
    commit('SET_CLEARING', value)
  },
  setUndoRedoState({ commit }, value) {
    commit('SET_UNDO_REDO_STATE', value)
  },
  setUserSessionExpired({ commit }, value) {
    commit('SET_USER_SESSION_EXPIRED', value)
  },
  setUserPasswordChanged({ commit }, value) {
    commit('SET_USER_PASSWORD_CHANGED', value)
  },
  setPermissionsUpdated({ commit }, value) {
    commit('SET_PERMISSIONS_UPDATED', value)
  },
  setWorkspaceOutdated({ commit }, value) {
    commit('SET_WORKSPACE_OUTDATED', value)
  },
  userLoggedOut({ commit }) {
    commit('SET_PERMISSIONS_UPDATED', false)
    commit('SET_COPYING', false)
    commit('SET_PASTING', false)
    commit('SET_CLEARING', false)
    commit('SET_UNDO_REDO_STATE', UNDO_REDO_STATES.HIDDEN)
    commit('SET_RECONNECTING', false)
    commit('SET_FAILED_CONNECTING', false)
    commit('SET_WORKSPACE_OUTDATED', false)
  },
}

export const getters = {
  undoRedoState(state) {
    return state.undoRedoState
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
