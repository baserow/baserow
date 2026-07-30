import { TestApp } from '@baserow/test/helpers/testApp'

describe('field store', () => {
  let testApp
  let store

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.store
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('refreshLoadedFieldErrors updates only errors of cached fields', async () => {
    await store.dispatch('field/forceSetFields', {
      fields: [
        {
          id: 1,
          table_id: 10,
          name: 'AI field',
          type: 'text',
          error: null,
        },
        {
          id: 2,
          table_id: 10,
          name: 'Invalid field',
          type: 'text',
          error: 'Existing error',
        },
      ],
    })
    store.commit('field/SET_LOADED', { tableId: 10, viewId: null })
    const originalField = store.getters['field/get'](1)

    testApp.mock.onGet('/database/fields/table/10/').reply(200, [
      {
        id: 1,
        table_id: 10,
        name: 'Changed server name',
        type: 'text',
        error: 'Model unavailable',
      },
      {
        id: 2,
        table_id: 10,
        name: 'Changed invalid field name',
        type: 'text',
        error: null,
      },
    ])

    await store.dispatch('field/refreshLoadedFieldErrors')

    expect(store.getters['field/get'](1)).toBe(originalField)
    expect(store.getters['field/get'](1)).toMatchObject({
      name: 'AI field',
      error: 'Model unavailable',
    })
    expect(store.getters['field/get'](2)).toMatchObject({
      name: 'Invalid field',
      error: null,
    })
  })
})
