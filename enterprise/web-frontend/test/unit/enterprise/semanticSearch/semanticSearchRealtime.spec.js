import { TestApp } from '@baserow/test/helpers/testApp'
import { registerRealtimeEvents } from '@baserow_enterprise/realtime'

describe('Semantic search realtime events', () => {
  let testApp = null

  beforeEach(() => {
    testApp = new TestApp()
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('updates the status of the field', () => {
    const handlers = {}
    registerRealtimeEvents({
      registerEvent: (name, handler) => {
        handlers[name] = handler
      },
    })
    const store = testApp.store
    store.commit('field/SET_ITEMS', [
      {
        id: 1,
        name: 'Notes',
        type: 'text',
        semantic_search_status: 'indexing',
      },
    ])

    handlers.semantic_search_field_status_updated(
      { store },
      { field_id: 1, semantic_search_status: 'ready' }
    )

    expect(store.getters['field/get'](1)).toMatchObject({
      name: 'Notes',
      semantic_search_status: 'ready',
    })
  })
})
