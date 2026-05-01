/**
 * Registers Whiteboard real-time event handlers on the shared $realtime
 * handler. Every event is filtered by `whiteboard_id` so a client only
 * processes messages that belong to the board it is currently viewing.
 */
export const registerRealtimeEvents = (realtime) => {
  realtime.registerEvent('whiteboard_content_updated', ({ store }, data) => {
    // Intentionally a no-op for clients that already have the board
    // open. Live edits arrive via `scene_update` broadcasts; this
    // PUT-success notification used to dispatch `fetchInitial`, which
    // RESETs the store and unmounts <ExcalidrawCollab> until the GET
    // resolves — a visible flicker on every autosave. Initial state
    // is loaded once in `pages/whiteboard.vue` `onMounted`, and any
    // subsequent reconnect re-runs that mount, so we don't need a
    // refetch here.
    void store
    void data
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

  // Comment events.
  const isCurrentBoard = (store, data) =>
    data.whiteboard_id ===
    store.getters['whiteboardApplication/getWhiteboardId']

  realtime.registerEvent('whiteboard_comment_created', ({ store }, data) => {
    if (!isCurrentBoard(store, data)) return
    store.dispatch('whiteboardComments/handleRemoteCreated', {
      comment: data.comment,
    })
  })

  realtime.registerEvent('whiteboard_comment_updated', ({ store }, data) => {
    if (!isCurrentBoard(store, data)) return
    store.dispatch('whiteboardComments/handleRemoteUpdated', {
      comment: data.comment,
    })
  })

  realtime.registerEvent('whiteboard_comment_deleted', ({ store }, data) => {
    if (!isCurrentBoard(store, data)) return
    store.dispatch('whiteboardComments/handleRemoteDeleted', {
      commentId: data.comment_id,
    })
  })

  realtime.registerEvent('whiteboard_comment_resolved', ({ store }, data) => {
    if (!isCurrentBoard(store, data)) return
    store.dispatch('whiteboardComments/handleRemoteResolved', {
      comment: data.comment,
    })
  })
}
