import _ from 'lodash'

import moment from '@baserow/modules/core/moment'

import RowCommentService from '@baserow_premium/services/row_comments/row_comments'

export const state = () => ({
  comments: [],
  loading: false,
  loaded: false,
  currentCount: 0,
  totalCount: 0,
  loadedRowId: false,
  loadedTableId: false,
  nextTemporaryCommentId: -1,
})

function populateComment(comment, loading) {
  comment._ = {
    loading,
  }
  return comment
}

async function updateRowMetadataInViews(
  store,
  tableId,
  rowId,
  rowMetadataKey,
  updateMetadataValueFunc
) {
  for (const viewType of Object.values(store.$registry.getAll('view'))) {
    await viewType.rowMetadataUpdated(
      { store },
      tableId,
      rowId,
      rowMetadataKey,
      updateMetadataValueFunc,
      'page/'
    )
  }
}

async function updateCommentCountInViews(store, rowComment, updateCountFunc) {
  // A new comment has been forcibly created/deleted so we need to let all views know that
  // the row comment count metadata should be changed atomically.
  await updateRowMetadataInViews(
    store,
    rowComment.table_id,
    rowComment.row_id,
    'row_comment_count',
    updateCountFunc
  )
}

async function increaseCommentCountInViews(store, rowComment) {
  await updateCommentCountInViews(store, rowComment, (count) =>
    count ? count + 1 : 1
  )
}

async function decreaseCommentCountInViews(store, rowComment) {
  await updateCommentCountInViews(store, rowComment, (count) =>
    count > 1 ? count - 1 : null
  )
}

export const mutations = {
  /**
   * Adds a list of comments to the existing comments, ensuring that the end result of
   * comments is an ordered list of comments descending by ID with no duplicate
   * comments. If a comment with the same id as an existing comment is provided in the
   * list the existing comment will be replaced by the new one.
   *
   * We want to handle duplicates here as comments received as realtime events could
   * potentially be also loaded in via a normal backend api fetch call.
   */
  ADD_ROW_COMMENTS(state, { comments, loading }) {
    comments.forEach((newComment) => {
      newComment = populateComment(newComment, loading)
      const existingIndex = state.comments.findIndex(
        (c) => c.id === newComment.id
      )
      if (existingIndex >= 0) {
        // Prevent duplicates by just replacing them inline
        state.comments.splice(existingIndex, 0, newComment)
      } else {
        state.comments.push(newComment)
      }
    })
    state.currentCount = state.comments.length
  },
  UPDATE_ROW_COMMENT(state, rowComment) {
    const existingIndex = state.comments.findIndex(
      (c) => c.id === rowComment.id
    )
    if (existingIndex >= 0) {
      const existingComment = Object.assign(
        {},
        state.comments[existingIndex],
        rowComment
      )
      existingComment.updated_on = moment(rowComment.updated_on).toISOString()
      state.comments.splice(existingIndex, 1, existingComment)
    }
  },
  SET_ROW_COMMENT_DELETED(state, { commentId, deleted, clearContent = true }) {
    const existingIndex = state.comments.findIndex((c) => c.id === commentId)
    if (existingIndex >= 0) {
      const deletedComment = Object.assign({}, state.comments[existingIndex], {
        trashed: deleted,
        comment: clearContent ? '' : state.comments[existingIndex].comment,
      })
      state.comments.splice(existingIndex, 1, deletedComment)
    }
  },
  REMOVE_ROW_COMMENT(state, id) {
    const existingIndex = state.comments.findIndex((c) => c.id === id)
    if (existingIndex >= 0) {
      state.comments.splice(existingIndex, 1)
    }
  },
  RESET_ROW_COMMENTS(state) {
    state.comments = []
  },
  SET_LOADING(state, loading) {
    state.loading = loading
  },
  SET_LOADED(state, loaded) {
    state.loaded = loaded
  },
  SET_NEXT_TEMPORARY_COMMENT_ID(state, nextTemporaryCommentId) {
    state.nextTemporaryCommentId = nextTemporaryCommentId
  },
  SET_LOADED_TABLE_AND_ROW(state, { tableId, rowId }) {
    state.loadedRowId = rowId
    state.loadedTableId = tableId
  },
  SET_TOTAL_COUNT(state, totalCount) {
    state.totalCount = totalCount
  },
}

export const actions = {
  /**
   * Fetches the initial row comments to display for a given table and row. Resets any
   * existing comments entirely.
   */
  async fetchRowComments({ commit }, { tableId, rowId }) {
    commit('SET_LOADING', true)
    commit('SET_LOADED', false)
    try {
      const { data } = await RowCommentService(this.$client).fetchAll(
        tableId,
        rowId,
        {}
      )
      commit('RESET_ROW_COMMENTS')
      commit('ADD_ROW_COMMENTS', { comments: data.results, loading: false })
      commit('SET_TOTAL_COUNT', data.count)
      commit('SET_LOADED_TABLE_AND_ROW', { tableId, rowId })
      commit('SET_LOADED', true)
    } finally {
      commit('SET_LOADING', false)
    }
  },
  /**
   * Fetches the next 10 comments from the server and adds them to the comments list.
   */
  async fetchNextSetOfComments({ commit, state }, { tableId, rowId }) {
    commit('SET_LOADING', true)
    try {
      // We have to use offset based paging here as new comments can be added by the
      // user or come in via realtime events.
      const { data } = await RowCommentService(this.$client).fetchAll(
        tableId,
        rowId,
        { offset: state.currentCount }
      )
      commit('ADD_ROW_COMMENTS', { comments: data.results, loading: false })
      commit('SET_TOTAL_COUNT', data.count)
    } finally {
      commit('SET_LOADING', false)
    }
  },
  /**
   * Posts a new comment to the server and updates the comments list once the server
   * responds with it's id and other related comment data.
   */
  async postComment(
    { commit, state, rootGetters, dispatch },

    { tableId, rowId, message }
  ) {
    const temporaryId = state.nextTemporaryCommentId
    commit('SET_NEXT_TEMPORARY_COMMENT_ID', temporaryId - 1)
    try {
      // Immediately add the row comment to the UI to be replaced by the real comment
      // later from the server.
      const temporaryComment = {
        created_on: moment().toISOString(),
        updated_on: moment().toISOString(),
        message,
        row_id: rowId,
        table_id: tableId,
        user_id: rootGetters['auth/getUserId'],
        first_name: rootGetters['auth/getName'],
        isTemporary: true,
        id: temporaryId,
      }
      commit('ADD_ROW_COMMENTS', {
        comments: [temporaryComment],
        loading: true,
      })
      const { data } = await RowCommentService(this.$client).create(
        tableId,
        rowId,
        message
      )
      commit('REMOVE_ROW_COMMENT', temporaryId)
      dispatch('forceCreate', { rowComment: data })
    } catch (e) {
      // Make sure we remove the temporary comment if the create call failed.
      commit('REMOVE_ROW_COMMENT', temporaryId)
      throw e
    }
  },
  async forceCreate({ commit, state }, { rowComment }) {
    if (
      state.loadedTableId === rowComment.table_id &&
      state.loadedRowId === rowComment.row_id
    ) {
      commit('ADD_ROW_COMMENTS', { comments: [rowComment], loading: false })
      commit('SET_TOTAL_COUNT', state.totalCount + 1)
    }
    await increaseCommentCountInViews(this, rowComment)
  },
  /**
   * Update a comment content.
   */
  async updateComment({ commit, getters }, { tableId, commentId, message }) {
    const comment = getters.getCommentById(commentId)
    const originalMessage = comment.message
    const originalUpdatedOn = comment.updated_on
    const originalEdited = comment.edited
    commit('UPDATE_ROW_COMMENT', {
      id: commentId,
      message,
      updated_on: moment().toISOString(),
      edited: true,
    })
    try {
      await RowCommentService(this.$client).update(tableId, commentId, message)
    } catch (e) {
      // Make sure we revert the comment if the update call failed.
      commit('UPDATE_ROW_COMMENT', {
        id: commentId,
        message: originalMessage,
        updated_on: originalUpdatedOn,
        edited: originalEdited,
      })
      throw e
    }
  },
  async forceUpdate({ commit, getters }, { rowComment }) {
    const originalComment = getters.getCommentById(rowComment.id)
    if (!originalComment) {
      return
    }
    // update comment count in views if needed
    if (originalComment.trashed !== rowComment.trashed) {
      const updateCountInViews = rowComment.trashed
        ? decreaseCommentCountInViews
        : increaseCommentCountInViews
      await updateCountInViews(this, rowComment)
    }
    commit('UPDATE_ROW_COMMENT', rowComment)
  },
  /**
   * Delete a row comment.
   */
  async deleteComment({ commit }, { tableId, commentId }) {
    commit('SET_ROW_COMMENT_DELETED', {
      commentId,
      deleted: true,
      clearContent: false,
    })
    try {
      const { data: rowComment } = await RowCommentService(this.$client).delete(
        tableId,
        commentId
      )
      await decreaseCommentCountInViews(this, rowComment)
      commit('UPDATE_ROW_COMMENT', rowComment)
    } catch (e) {
      commit('SET_ROW_COMMENT_DELETED', { commentId, deleted: false })
      throw e
    }
  },
  /**
   * Update the notification mode for comments on a row.
   */
  async updateNotificationMode({ dispatch }, { table, row, mode }) {
    const originalMode = row._.metadata.row_comments_notification_mode

    try {
      await dispatch('forceUpdateNotificationMode', {
        tableId: table.id,
        rowId: row.id,
        mode,
      })
      await RowCommentService(this.$client).updateNotificationMode(
        table.id,
        row.id,
        mode
      )
    } catch (e) {
      await dispatch('forceUpdateNotificationMode', {
        tableId: table.id,
        rowId: row.id,
        mode: originalMode,
      })
      throw e
    }
  },
  /**
   * Forcefully update the notification mode for a comments on a row.
   */
  async forceUpdateNotificationMode({ dispatch }, { tableId, rowId, mode }) {
    const updateFunction = () => mode.toString()
    const rowMetadataType = 'row_comments_notification_mode'
    await updateRowMetadataInViews(
      this,
      tableId,
      rowId,
      rowMetadataType,
      updateFunction
    )
    // Let's also make sure the local copy of the row edit modal is updated in case the
    // row is not in any view buffer.
    dispatch(
      'rowModal/updateRowMetadata',
      { rowId, rowMetadataType, updateFunction },
      { root: true }
    )
  },
}

export const getters = {
  getSortedRowComments(state) {
    return _.sortBy(state.comments, (c) => -moment.utc(c.created_on))
  },
  getCurrentCount(state) {
    return state.currentCount
  },
  getTotalCount(state) {
    return state.totalCount
  },
  getLoading(state) {
    return state.loading
  },
  getLoaded(state) {
    return state.loaded
  },
  getCommentById: (state) => (commentId) => {
    return state.comments.find((c) => c.id === commentId)
  },
}

export default {
  namespaced: true,
  state,
  getters,
  actions,
  mutations,
}
