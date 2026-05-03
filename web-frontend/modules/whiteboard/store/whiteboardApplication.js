import WhiteboardService from '@baserow/modules/whiteboard/services/whiteboard'

export const state = () => ({
  whiteboardId: null,
  loading: false,
  content: { elements: [], appState: {}, files: {} },
  pendingRemoteUpdates: [],
  collaborators: {},
  // Bumped every time a peer asks us to (re)broadcast our current
  // viewport — used to make the "follow user" feature work
  // immediately on click. Channels doesn't replay broadcasts on
  // subscribe, so a freshly-joined client otherwise has no viewport
  // for an idle peer until that peer pans or zooms.
  viewportRequestSeq: 0,
})

export const mutations = {
  RESET(state) {
    state.whiteboardId = null
    state.content = { elements: [], appState: {}, files: {} }
    state.pendingRemoteUpdates = []
    state.collaborators = {}
    state.viewportRequestSeq = 0
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
    // Merge into the existing entry rather than replace it. Pointer
    // updates fire on every mouse move and were wiping the
    // `viewport` field (set by `SET_COLLABORATOR_VIEWPORT`) — which
    // broke instant follow because the cached viewport disappeared
    // between the last pan/zoom broadcast and the moment the user
    // clicked the avatar.
    const existing = state.collaborators[collaborator.id]
    state.collaborators = {
      ...state.collaborators,
      [collaborator.id]: { ...(existing || {}), ...collaborator },
    }
  },
  SET_COLLABORATOR_VIEWPORT(
    state,
    { id, scrollX, scrollY, zoom, width, height }
  ) {
    // Don't auto-create a collaborator entry if we haven't seen a
    // pointer/cursor signal from this user yet — Excalidraw's
    // collaborators map keys off the same id, and a synthetic entry
    // with no name/colour would render an unnamed avatar.
    const existing = state.collaborators[id]
    if (!existing) return
    state.collaborators = {
      ...state.collaborators,
      [id]: {
        ...existing,
        viewport: { scrollX, scrollY, zoom, width, height },
      },
    }
  },
  REMOVE_COLLABORATOR(state, userId) {
    const next = { ...state.collaborators }
    delete next[userId]
    state.collaborators = next
  },
  INCREMENT_VIEWPORT_REQUEST_SEQ(state) {
    state.viewportRequestSeq += 1
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
  broadcastChanges({ state }, payload) {
    if (!state.whiteboardId) return
    // Send the ephemeral collab payload directly over the existing
    // authenticated WebSocket connection. The previous HTTP route
    // (`POST /whiteboard/<id>/broadcast-changes/`) had to re-auth on
    // every keystroke and went through DRF + a Django worker, which
    // didn't scale on a busy board. The WS connection is already
    // open and `client_message_registry` dispatches the payload to
    // the same `WhiteboardPageType` group via Channels.
    //
    // We reach `$realtime` through `this.app` (the Nuxt app context).
    // `storeRegister.js` does NOT inject `$realtime` directly onto the
    // store because the realtime plugin depends on the store at boot
    // time (would be a circular dep), but `this.app.$realtime` is
    // populated long before any user interaction can trigger a
    // broadcast.
    const $realtime = this.app?.$realtime
    if (!$realtime) return
    $realtime.send({
      type: 'broadcast_whiteboard_changes',
      whiteboard_id: state.whiteboardId,
      payload,
    })
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
  setCollaboratorViewport({ commit }, payload) {
    commit('SET_COLLABORATOR_VIEWPORT', payload)
  },
  noteViewportRequest({ commit }) {
    commit('INCREMENT_VIEWPORT_REQUEST_SEQ')
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
  getViewportRequestSeq(state) {
    return state.viewportRequestSeq
  },
}

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters,
}
