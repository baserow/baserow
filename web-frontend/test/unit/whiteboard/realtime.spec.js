import { registerRealtimeEvents } from '@baserow/modules/whiteboard/realtime'
import { expect, test, vi } from 'vitest'

describe('Whiteboard realtime events', () => {
  let realtime
  let registeredEvents

  beforeEach(() => {
    registeredEvents = {}
    realtime = {
      registerEvent(type, callback) {
        registeredEvents[type] = callback
      },
    }
    registerRealtimeEvents(realtime)
  })

  test('registers whiteboard_changes event', () => {
    expect(registeredEvents).toHaveProperty('whiteboard_changes')
  })

  test('registers whiteboard_content_updated event', () => {
    expect(registeredEvents).toHaveProperty('whiteboard_content_updated')
  })

  test('whiteboard_changes dispatches applyRemoteChanges when matching whiteboard', () => {
    const dispatch = vi.fn()
    const store = {
      getters: {
        'whiteboardApplication/getWhiteboardId': 42,
      },
      dispatch,
    }

    const changes = { added: { 'shape:1': { id: 'shape:1' } } }
    registeredEvents.whiteboard_changes(
      { store },
      { whiteboard_id: 42, changes }
    )

    expect(dispatch).toHaveBeenCalledWith(
      'whiteboardApplication/applyRemoteChanges',
      changes
    )
  })

  test('whiteboard_changes ignores non-matching whiteboard', () => {
    const dispatch = vi.fn()
    const store = {
      getters: {
        'whiteboardApplication/getWhiteboardId': 42,
      },
      dispatch,
    }

    registeredEvents.whiteboard_changes(
      { store },
      { whiteboard_id: 99, changes: {} }
    )

    expect(dispatch).not.toHaveBeenCalled()
  })
})
