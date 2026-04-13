export const registerRealtimeEvents = (realtime) => {
  realtime.registerEvent('whiteboard_changes', ({ store }, data) => {
    if (
      data.whiteboard_id ===
      store.getters['whiteboardApplication/getWhiteboardId']
    ) {
      store.dispatch('whiteboardApplication/applyRemoteChanges', data.changes)
    }
  })
  realtime.registerEvent('whiteboard_content_updated', ({ store }, data) => {
    if (
      data.whiteboard_id ===
      store.getters['whiteboardApplication/getWhiteboardId']
    ) {
      // Another user saved the full snapshot. Refetch the latest content so
      // our local state stays up-to-date with the persisted version. This
      // acts as an eventual-consistency fallback alongside the individual
      // shape-level changes broadcast via whiteboard_changes.
      store.dispatch('whiteboardApplication/fetchContent', data.whiteboard_id)
    }
  })
}
