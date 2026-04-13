import WhiteboardService from '@baserow/modules/whiteboard/services/whiteboard'

export const state = () => ({
  whiteboardId: null,
  loading: false,
  content: {},
  // Queue of remote changes to be applied by TldrawEditor.
  // Each mutation creates a new array reference so Vue watchers detect it.
  pendingRemoteChanges: [],
})

export const mutations = {
  RESET(state) {
    state.whiteboardId = null
    state.loading = false
    state.content = {}
    state.pendingRemoteChanges = []
  },
  SET_WHITEBOARD_ID(state, whiteboardId) {
    state.whiteboardId = whiteboardId
  },
  SET_LOADING(state, value) {
    state.loading = value
  },
  SET_CONTENT(state, content) {
    state.content = content
  },
  PUSH_REMOTE_CHANGES(state, changes) {
    // Create a new array to ensure Vue reactivity detects the change.
    state.pendingRemoteChanges = [...state.pendingRemoteChanges, changes]
  },
  CLEAR_REMOTE_CHANGES(state) {
    state.pendingRemoteChanges = []
  },
}

export const actions = {
  setLoading({ commit }, value) {
    commit('SET_LOADING', value)
  },
  reset({ commit }) {
    commit('RESET')
  },
  async fetchInitial({ commit }, { whiteboardId }) {
    const { $client } = this
    commit('RESET')
    // Keep loading=true so TldrawEditor does not mount with empty content
    // before the API call returns. RESET sets loading=false, so we
    // immediately override it here.
    commit('SET_LOADING', true)
    commit('SET_WHITEBOARD_ID', whiteboardId)
    try {
      const { data } = await WhiteboardService($client).getContent(whiteboardId)
      commit('SET_CONTENT', data.content || {})
    } catch (error) {
      commit('SET_CONTENT', {})
    }
    commit('SET_LOADING', false)
  },
  async saveContent({ state }, content) {
    const { $client } = this
    if (!state.whiteboardId) return
    await WhiteboardService($client).saveContent(state.whiteboardId, content)
  },
  async broadcastChanges({ state }, changes) {
    const { $client } = this
    if (!state.whiteboardId) return
    await WhiteboardService($client).broadcastChanges(
      state.whiteboardId,
      changes
    )
  },
  async fetchContent({ commit, state }) {
    const { $client } = this
    if (!state.whiteboardId) return
    try {
      const { data } = await WhiteboardService($client).getContent(
        state.whiteboardId
      )
      commit('SET_CONTENT', data.content || {})
    } catch (error) {
      // Ignore fetch errors silently
    }
  },
  updateContent({ commit }, content) {
    commit('SET_CONTENT', content)
  },
  applyRemoteChanges({ commit }, changes) {
    commit('PUSH_REMOTE_CHANGES', changes)
  },
  clearRemoteChanges({ commit }) {
    commit('CLEAR_REMOTE_CHANGES')
  },
}

export const getters = {
  getWhiteboardId(state) {
    return state.whiteboardId
  },
  isLoading(state) {
    return state.loading
  },
  getContent(state) {
    return state.content
  },
  getPendingRemoteChanges(state) {
    return state.pendingRemoteChanges
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
