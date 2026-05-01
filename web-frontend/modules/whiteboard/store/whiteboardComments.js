import WhiteboardCommentService from '@baserow/modules/whiteboard/services/whiteboardComment'

const DRAFT_THREAD_ID = 'draft'

export const state = () => ({
  comments: [],
  commentModeActive: false,
  showResolved: false,
  draftPin: null, // { x, y }
  openThreadId: null,
  loadingByCommentId: {}, // { [id]: 'updating' | 'deleting' | 'resolving' }
  postingDraft: false,
  postingReplyForThreadId: null,
})

export const mutations = {
  RESET(state) {
    state.comments = []
    state.commentModeActive = false
    state.showResolved = false
    state.draftPin = null
    state.openThreadId = null
    state.loadingByCommentId = {}
    state.postingDraft = false
    state.postingReplyForThreadId = null
  },
  SET_COMMENTS(state, comments) {
    state.comments = comments
  },
  UPSERT_COMMENT(state, comment) {
    const idx = state.comments.findIndex((c) => c.id === comment.id)
    if (idx === -1) {
      state.comments = [...state.comments, comment]
    } else {
      const next = [...state.comments]
      next[idx] = comment
      state.comments = next
    }
  },
  REMOVE_COMMENT(state, commentId) {
    // Cascade — drop replies whose parent_comment_id matches
    state.comments = state.comments.filter(
      (c) => c.id !== commentId && c.parent_comment_id !== commentId
    )
  },
  SET_COMMENT_MODE_ACTIVE(state, active) {
    state.commentModeActive = active
  },
  SET_SHOW_RESOLVED(state, show) {
    state.showResolved = show
  },
  SET_DRAFT_PIN(state, draft) {
    state.draftPin = draft
  },
  SET_OPEN_THREAD_ID(state, id) {
    state.openThreadId = id
  },
  SET_LOADING_FOR_COMMENT(state, { id, value }) {
    if (value == null) {
      const next = { ...state.loadingByCommentId }
      delete next[id]
      state.loadingByCommentId = next
    } else {
      state.loadingByCommentId = { ...state.loadingByCommentId, [id]: value }
    }
  },
  SET_POSTING_DRAFT(state, value) {
    state.postingDraft = value
  },
  SET_POSTING_REPLY_FOR(state, threadId) {
    state.postingReplyForThreadId = threadId
  },
}

export const actions = {
  async fetchAll({ commit }, { whiteboardId }) {
    const { $client } = this
    const { data } =
      await WhiteboardCommentService($client).listComments(whiteboardId)
    commit('SET_COMMENTS', data)
  },
  reset({ commit }) {
    commit('RESET')
  },
  setCommentModeActive({ commit }, active) {
    commit('SET_COMMENT_MODE_ACTIVE', active)
  },
  setShowResolved({ commit }, show) {
    commit('SET_SHOW_RESOLVED', show)
  },
  openDraftPin({ commit }, { x, y }) {
    commit('SET_DRAFT_PIN', { x, y })
    commit('SET_OPEN_THREAD_ID', DRAFT_THREAD_ID)
    commit('SET_COMMENT_MODE_ACTIVE', false)
  },
  cancelDraftPin({ commit, state }) {
    commit('SET_DRAFT_PIN', null)
    if (state.openThreadId === DRAFT_THREAD_ID) {
      commit('SET_OPEN_THREAD_ID', null)
    }
  },
  openThread({ commit }, threadId) {
    commit('SET_OPEN_THREAD_ID', threadId)
  },
  closeThread({ commit, state }) {
    if (state.openThreadId === DRAFT_THREAD_ID) {
      commit('SET_DRAFT_PIN', null)
    }
    commit('SET_OPEN_THREAD_ID', null)
  },
  async postDraftComment(
    { commit, state, dispatch },
    { whiteboardId, message }
  ) {
    const { $client } = this
    if (!state.draftPin) return null
    const { x, y } = state.draftPin
    commit('SET_POSTING_DRAFT', true)
    try {
      const { data } = await WhiteboardCommentService($client).createComment(
        whiteboardId,
        { message, x, y }
      )
      commit('UPSERT_COMMENT', data)
      commit('SET_DRAFT_PIN', null)
      commit('SET_OPEN_THREAD_ID', data.id)
      return data
    } finally {
      commit('SET_POSTING_DRAFT', false)
    }
  },
  async postReply({ commit }, { whiteboardId, parentCommentId, message }) {
    const { $client } = this
    commit('SET_POSTING_REPLY_FOR', parentCommentId)
    try {
      const { data } = await WhiteboardCommentService($client).createComment(
        whiteboardId,
        { message, parentCommentId }
      )
      commit('UPSERT_COMMENT', data)
      return data
    } finally {
      commit('SET_POSTING_REPLY_FOR', null)
    }
  },
  async updateComment({ commit }, { commentId, message }) {
    const { $client } = this
    commit('SET_LOADING_FOR_COMMENT', { id: commentId, value: 'updating' })
    try {
      const { data } = await WhiteboardCommentService($client).updateComment(
        commentId,
        message
      )
      commit('UPSERT_COMMENT', data)
      return data
    } finally {
      commit('SET_LOADING_FOR_COMMENT', { id: commentId, value: null })
    }
  },
  async deleteComment({ commit }, { commentId }) {
    const { $client } = this
    commit('SET_LOADING_FOR_COMMENT', { id: commentId, value: 'deleting' })
    try {
      await WhiteboardCommentService($client).deleteComment(commentId)
      commit('REMOVE_COMMENT', commentId)
    } finally {
      commit('SET_LOADING_FOR_COMMENT', { id: commentId, value: null })
    }
  },
  async setResolved({ commit }, { commentId, resolved }) {
    const { $client } = this
    commit('SET_LOADING_FOR_COMMENT', { id: commentId, value: 'resolving' })
    try {
      const { data } = await WhiteboardCommentService($client).resolveComment(
        commentId,
        resolved
      )
      commit('UPSERT_COMMENT', data)
      return data
    } finally {
      commit('SET_LOADING_FOR_COMMENT', { id: commentId, value: null })
    }
  },
  // Realtime handlers — idempotent upserts so a peer receiving the WS
  // event after the optimistic local state simply replaces the row.
  handleRemoteCreated({ commit }, { comment }) {
    commit('UPSERT_COMMENT', comment)
  },
  handleRemoteUpdated({ commit }, { comment }) {
    commit('UPSERT_COMMENT', comment)
  },
  handleRemoteDeleted({ commit, state }, { commentId }) {
    commit('REMOVE_COMMENT', commentId)
    if (state.openThreadId === commentId) {
      commit('SET_OPEN_THREAD_ID', null)
    }
  },
  handleRemoteResolved({ commit }, { comment }) {
    commit('UPSERT_COMMENT', comment)
  },
}

export const getters = {
  getComments(state) {
    return state.comments
  },
  /**
   * Top-level threads (with their replies attached). Resolved threads
   * are filtered out unconditionally — the UI does not surface them
   * once they're done.
   */
  getThreads(state) {
    const repliesByParent = {}
    for (const c of state.comments) {
      if (c.parent_comment_id) {
        ;(repliesByParent[c.parent_comment_id] ??= []).push(c)
      }
    }
    return state.comments
      .filter((c) => !c.parent_comment_id && !c.resolved)
      .map((thread) => ({
        ...thread,
        replies: (repliesByParent[thread.id] || []).sort(
          (a, b) => new Date(a.created_on) - new Date(b.created_on)
        ),
      }))
  },
  getThreadById: (state) => (id) => {
    const thread = state.comments.find(
      (c) => c.id === id && !c.parent_comment_id
    )
    if (!thread) return null
    const replies = state.comments
      .filter((c) => c.parent_comment_id === id)
      .sort((a, b) => new Date(a.created_on) - new Date(b.created_on))
    return { ...thread, replies }
  },
  getCommentLoadingState: (state) => (id) => {
    return state.loadingByCommentId[id] || null
  },
  getDraftPin(state) {
    return state.draftPin
  },
  getOpenThreadId(state) {
    return state.openThreadId
  },
  isCommentModeActive(state) {
    return state.commentModeActive
  },
  getShowResolved(state) {
    return state.showResolved
  },
  isPostingDraft(state) {
    return state.postingDraft
  },
  getPostingReplyForThreadId(state) {
    return state.postingReplyForThreadId
  },
  hasUnresolvedThread(state) {
    return state.comments.some((c) => !c.parent_comment_id && !c.resolved)
  },
}

export default {
  namespaced: true,
  state,
  mutations,
  actions,
  getters,
}
