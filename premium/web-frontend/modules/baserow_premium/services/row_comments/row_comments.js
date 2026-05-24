function buildViewIdParam(viewId) {
  return viewId ? `&view=${viewId}` : ''
}

export default (client) => {
  return {
    fetchAll(tableId, rowId, { offset = 0, limit = 50, viewId = null }) {
      return client.get(
        `/row_comments/${tableId}/${rowId}/?offset=${offset}&limit=${limit}${buildViewIdParam(viewId)}`
      )
    },
    create(tableId, rowId, message, { viewId = null } = {}) {
      return client.post(
        `/row_comments/${tableId}/${rowId}/?${buildViewIdParam(viewId)}`,
        {
          message,
        }
      )
    },
    update(tableId, commentId, message, { viewId = null } = {}) {
      return client.patch(
        `/row_comments/${tableId}/comment/${commentId}/?${buildViewIdParam(viewId)}`,
        {
          message,
        }
      )
    },
    delete(tableId, commentId, { viewId = null } = {}) {
      return client.delete(
        `/row_comments/${tableId}/comment/${commentId}/?${buildViewIdParam(viewId)}`
      )
    },
    updateNotificationMode(tableId, rowId, mode, { viewId = null } = {}) {
      return client.put(
        `/row_comments/${tableId}/${rowId}/notification-mode/?${buildViewIdParam(viewId)}`,
        { mode }
      )
    },
  }
}
