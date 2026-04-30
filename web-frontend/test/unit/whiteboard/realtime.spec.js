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
      'whiteboard_content_updated',
    ])
  })

  test('whiteboard_content_updated dispatches fetchInitial when ids match', () => {
    const store = makeStore(7)
    handlers.whiteboard_content_updated({ store }, { whiteboard_id: 7 })
    expect(store.dispatch).toHaveBeenCalledWith(
      'whiteboardApplication/fetchInitial',
      { whiteboardId: 7 }
    )
  })

  test('whiteboard_content_updated ignores other boards', () => {
    const store = makeStore(7)
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
