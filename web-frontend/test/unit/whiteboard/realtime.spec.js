import { describe, expect, test, vi, beforeEach } from 'vitest'
import { registerRealtimeEvents } from '@baserow/modules/whiteboard/realtime'

const makeStore = (whiteboardId) => ({
  dispatch: vi.fn(),
  getters: {
    'whiteboardApplication/getWhiteboardId': whiteboardId,
  },
})

const buildRealtime = () => {
  const handlers = {}
  const realtime = {
    registerEvent(name, callback) {
      handlers[name] = callback
    },
  }
  return { handlers, realtime }
}

describe('whiteboard realtime', () => {
  let handlers
  let realtime

  beforeEach(() => {
    ;({ handlers, realtime } = buildRealtime())
    registerRealtimeEvents(realtime)
  })

  test('registers all expected events', () => {
    expect(Object.keys(handlers).sort()).toEqual([
      'pointer_update',
      'scene_update',
      'user_left_whiteboard',
      'viewport_request',
      'viewport_update',
      'whiteboard_comment_created',
      'whiteboard_comment_deleted',
      'whiteboard_comment_resolved',
      'whiteboard_comment_updated',
      'whiteboard_content_updated',
    ])
  })

  test('viewport_request increments the request counter', () => {
    const store = makeStore(7)
    handlers.viewport_request({ store }, { whiteboard_id: 7 })
    expect(store.dispatch).toHaveBeenCalledWith(
      'whiteboardApplication/noteViewportRequest'
    )
  })

  test('viewport_request ignores other boards', () => {
    const store = makeStore(7)
    handlers.viewport_request({ store }, { whiteboard_id: 99 })
    expect(store.dispatch).not.toHaveBeenCalled()
  })

  test('viewport_update dispatches setCollaboratorViewport with bounds', () => {
    const store = makeStore(7)
    handlers.viewport_update(
      { store },
      {
        whiteboard_id: 7,
        user_id: 11,
        scrollX: 100,
        scrollY: 200,
        zoom: 1.5,
        width: 1920,
        height: 1080,
      }
    )
    expect(store.dispatch).toHaveBeenCalledWith(
      'whiteboardApplication/setCollaboratorViewport',
      {
        id: 11,
        scrollX: 100,
        scrollY: 200,
        zoom: 1.5,
        width: 1920,
        height: 1080,
      }
    )
  })

  test('viewport_update ignores other boards', () => {
    const store = makeStore(7)
    handlers.viewport_update(
      { store },
      {
        whiteboard_id: 99,
        user_id: 11,
        scrollX: 0,
        scrollY: 0,
        zoom: 1,
        width: 100,
        height: 100,
      }
    )
    expect(store.dispatch).not.toHaveBeenCalled()
  })

  test('whiteboard_content_updated does not refetch (handled by scene_update)', () => {
    // Live changes are propagated via `scene_update` broadcasts, so
    // PUT-success events used to drive a flicker-causing fetchInitial
    // — they're now no-ops. Both ID-match and ID-mismatch should
    // dispatch nothing.
    const store = makeStore(7)
    handlers.whiteboard_content_updated({ store }, { whiteboard_id: 7 })
    handlers.whiteboard_content_updated({ store }, { whiteboard_id: 99 })
    expect(store.dispatch).not.toHaveBeenCalled()
  })

  test('scene_update queues a remote update with elements and files', () => {
    const store = makeStore(7)
    handlers.scene_update(
      { store },
      {
        whiteboard_id: 7,
        elements: [{ id: 'a' }],
        files: { f1: { id: 'f1' } },
      }
    )
    expect(store.dispatch).toHaveBeenCalledWith(
      'whiteboardApplication/queueRemoteUpdate',
      { kind: 'scene', elements: [{ id: 'a' }], files: { f1: { id: 'f1' } } }
    )
  })

  test('pointer_update updates the collaborator entry', () => {
    const store = makeStore(7)
    handlers.pointer_update(
      { store },
      {
        whiteboard_id: 7,
        user_id: 11,
        username: 'Alice',
        color: '#abc',
        pointer: { x: 1, y: 2 },
        button: 'down',
      }
    )
    expect(store.dispatch).toHaveBeenCalledWith(
      'whiteboardApplication/setCollaborator',
      {
        id: 11,
        username: 'Alice',
        color: '#abc',
        pointer: { x: 1, y: 2 },
        button: 'down',
      }
    )
  })

  test('user_left_whiteboard removes the collaborator', () => {
    const store = makeStore(7)
    handlers.user_left_whiteboard({ store }, { whiteboard_id: 7, user_id: 11 })
    expect(store.dispatch).toHaveBeenCalledWith(
      'whiteboardApplication/removeCollaborator',
      11
    )
  })
})
