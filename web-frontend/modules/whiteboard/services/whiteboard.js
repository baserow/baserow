export default (client) => {
  return {
    getContent(whiteboardId) {
      return client.get(`/whiteboard/${whiteboardId}/`)
    },
    saveContent(whiteboardId, content) {
      return client.put(`/whiteboard/${whiteboardId}/`, { content })
    },
    broadcastChanges(whiteboardId, payload) {
      return client.post(`/whiteboard/${whiteboardId}/broadcast-changes/`, {
        payload,
      })
    },
  }
}
