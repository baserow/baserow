export default (client) => {
  return {
    listComments(whiteboardId) {
      return client.get(`/whiteboard/${whiteboardId}/comments/`)
    },
    createComment(
      whiteboardId,
      { message, x = null, y = null, parentCommentId = null }
    ) {
      const body = { message }
      if (x !== null && x !== undefined) body.x = x
      if (y !== null && y !== undefined) body.y = y
      if (parentCommentId != null) body.parent_comment_id = parentCommentId
      return client.post(`/whiteboard/${whiteboardId}/comments/`, body)
    },
    updateComment(commentId, message) {
      return client.patch(`/whiteboard/comments/${commentId}/`, { message })
    },
    deleteComment(commentId) {
      return client.delete(`/whiteboard/comments/${commentId}/`)
    },
    resolveComment(commentId, resolved) {
      return client.post(`/whiteboard/comments/${commentId}/resolve/`, {
        resolved,
      })
    },
  }
}
