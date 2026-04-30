import WhiteboardService from '@baserow/modules/whiteboard/services/whiteboard'

export const state = () => ({
  whiteboardId: null,
  loading: false,
  content: { elements: [], appState: {}, files: {} },
  pendingRemoteUpdates: [],
  collaborators: {},
})

export const mutations = {
  RESET(state) {
    state.whiteboardId = null
    state.content = { elements: [], appState: {}, files: {} }
    state.pendingRemoteUpdates = []
    state.collaborators = {}
  },
  SET_WHITEBOARD_ID(state, whiteboardId) {
    state.whiteboardId = whiteboardId
  },
  SET_LOADING(state, value) {
    state.loading = value
  },
  SET_CONTENT(state, content) {
    state.content = content || { elements: [], appState: {}, files: {} }
  },
  QUEUE_REMOTE_UPDATE(state, update) {
    state.pendingRemoteUpdates = [...state.pendingRemoteUpdates, update]
  },
  CLEAR_REMOTE_UPDATES(state) {
    state.pendingRemoteUpdates = []
  },
  SET_COLLABORATOR(state, collaborator) {
    state.collaborators = {
      ...state.collaborators,
      [collaborator.id]: collaborator,
    }
  },
  REMOVE_COLLABORATOR(state, userId) {
    const next = { ...state.collaborators }
    delete next[userId]
    state.collaborators = next
  },
}

export const actions = {
  setLoading({ commit }, value) {
    commit('SET_LOADING', value)
  },
  async fetchInitial({ commit }, { whiteboardId }) {
    const { $client } = this
    commit('RESET')
    const { data } = await WhiteboardService($client).getContent(whiteboardId)
    commit('SET_CONTENT', data.content || {})
    // Commit the whiteboard id LAST. The page's `contentLoaded` flag
    // gates `<ExcalidrawCollab>` on `state.whiteboardId != null`, so
    // until SET_CONTENT has actually run we must keep the id null —
    // otherwise the component would mount, read the still-empty
    // default `state.content` from the RESET above as its
    // `initialData`, fire onChange with `elements: []`, and the
    // autosave 3 s later would wipe the persisted scene.
    commit('SET_WHITEBOARD_ID', whiteboardId)
    commit('SET_LOADING', false)
  },
  async saveContent({ state }, content) {
    const { $client } = this
    if (!state.whiteboardId) return
    await WhiteboardService($client).saveContent(state.whiteboardId, content)
  },
  async broadcastChanges({ state }, payload) {
    const { $client } = this
    if (!state.whiteboardId) return
    try {
      await WhiteboardService($client).broadcastChanges(
        state.whiteboardId,
        payload
      )
    } catch (e) {
      // Ephemeral broadcasts must never break the editor — log and swallow.
      console.warn('whiteboard broadcastChanges failed', e)
    }
  },
  queueRemoteUpdate({ commit }, update) {
    commit('QUEUE_REMOTE_UPDATE', update)
  },
  clearRemoteUpdates({ commit }) {
    commit('CLEAR_REMOTE_UPDATES')
  },
  setCollaborator({ commit }, collaborator) {
    commit('SET_COLLABORATOR', collaborator)
  },
  removeCollaborator({ commit }, userId) {
    commit('REMOVE_COLLABORATOR', userId)
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
  getPendingRemoteUpdates(state) {
    return state.pendingRemoteUpdates
  },
  getCollaborators(state) {
    return state.collaborators
  },
}

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters,
}
