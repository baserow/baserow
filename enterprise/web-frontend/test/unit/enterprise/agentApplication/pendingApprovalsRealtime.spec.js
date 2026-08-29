import { expect } from 'vitest'

import { registerRealtimeEvents } from '@baserow_enterprise/realtime'

describe('agent_pending_approvals_updated realtime event', () => {
  let store = null
  let events = null

  beforeEach(() => {
    const { $store } = useNuxtApp()
    store = $store
    events = {}
    registerRealtimeEvents({
      registerEvent(name, handler) {
        events[name] = handler
      },
    })
  })

  test('updates the application in the core store', async () => {
    const application = await store.dispatch('application/forceCreate', {
      id: 42,
      type: 'agent',
      name: 'Agent app',
      order: 1,
      workspace: { id: 1 },
      pending_approvals_count: 0,
    })
    expect(application.pending_approvals_count).toBe(0)

    await events.agent_pending_approvals_updated(
      { store },
      { application_id: 42, count: 3 }
    )

    expect(store.getters['application/get'](42).pending_approvals_count).toBe(3)

    await events.agent_pending_approvals_updated(
      { store },
      { application_id: 42, count: 0 }
    )

    expect(store.getters['application/get'](42).pending_approvals_count).toBe(0)
  })

  test('ignores applications that are not in the store', () => {
    expect(() =>
      events.agent_pending_approvals_updated(
        { store },
        { application_id: 999999, count: 2 }
      )
    ).not.toThrow()
    expect(store.getters['application/get'](999999)).toBeUndefined()
  })
})
