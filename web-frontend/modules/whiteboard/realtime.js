/**
 * Registers Whiteboard real-time event handlers on the shared $realtime
 * handler. Every event is filtered by `whiteboard_id` so a client only
 * processes messages that belong to the board it is currently viewing.
 */
export const registerRealtimeEvents = (realtime) => {
  realtime.registerEvent('whiteboard_content_updated', ({ store }, data) => {
    if (
      data.whiteboard_id !==
      store.getters['whiteboardApplication/getWhiteboardId']
    ) {
      return
    }
    store.dispatch('whiteboardApplication/fetchInitial', {
      whiteboardId: data.whiteboard_id,
    })
  })

  realtime.registerEvent('scene_update', ({ store }, data) => {
    if (
      data.whiteboard_id !==
      store.getters['whiteboardApplication/getWhiteboardId']
    ) {
      return
    }
    store.dispatch('whiteboardApplication/queueRemoteUpdate', {
      kind: 'scene',
      elements: data.elements || [],
      files: data.files || {},
    })
  })

  realtime.registerEvent('pointer_update', ({ store }, data) => {
    if (
      data.whiteboard_id !==
      store.getters['whiteboardApplication/getWhiteboardId']
    ) {
      return
    }
    store.dispatch('whiteboardApplication/setCollaborator', {
      id: data.user_id,
      username: data.username,
      color: data.color,
      pointer: data.pointer,
      button: data.button,
    })
  })

  realtime.registerEvent('user_left_whiteboard', ({ store }, data) => {
    if (
      data.whiteboard_id !==
      store.getters['whiteboardApplication/getWhiteboardId']
    ) {
      return
    }
    store.dispatch('whiteboardApplication/removeCollaborator', data.user_id)
  })
}
