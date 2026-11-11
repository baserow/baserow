import { describe, expect, test, vi } from 'vitest'
import { registerChatRunRealtimeEvents } from '@baserow/modules/core/chatRuns/realtime'

describe('core run lifecycle discovery', () => {
  const handlers = {}
  registerChatRunRealtimeEvents({
    registerEvent: (name, handler) => {
      handlers[name] = handler
    },
  })

  test('announces run identity without carrying streamed output', () => {
    const store = { dispatch: vi.fn() }
    handlers.chat_run_changed(
      { store },
      { run_id: 'run', run_type: 'fake', chat_id: 7, status: 'running' }
    )
    expect(store.dispatch).toHaveBeenCalledExactlyOnceWith(
      'chatRuns/handleChanged',
      { runId: 'run', runType: 'fake', chatId: 7 }
    )
    expect(handlers.chat_run_events).toBeUndefined()
  })

  test('reconnect confirms the selected chat subscription', () => {
    const store = { dispatch: vi.fn() }
    handlers.page_add(
      { store },
      { page: 'chat_runs', parameters: { run_type: 'fake', chat_id: 7 } }
    )
    handlers.page_add({ store }, { page: 'table', parameters: { id: 8 } })
    expect(store.dispatch).toHaveBeenCalledExactlyOnceWith(
      'chatRuns/handlePageAdd',
      { run_type: 'fake', chat_id: 7 }
    )
  })
})
