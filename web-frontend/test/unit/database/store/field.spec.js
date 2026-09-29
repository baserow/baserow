import { vi } from 'vitest'
import flushPromises from 'flush-promises'

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

  const workspaceWithTable = async () => {
    await store.dispatch('workspace/forceCreate', { id: 1, name: 'Workspace' })
    store.commit('workspace/SET_PERMISSIONS', {
      workspaceId: 1,
      permissions: [],
    })
    await store.dispatch('application/forceCreate', {
      id: 5,
      type: 'database',
      workspace: { id: 1 },
      tables: [{ id: 10, name: 'Table', database_id: 5 }],
    })
    return { id: 10, database_id: 5 }
  }

  const permissionRequests = () =>
    testApp.mock.history.get.filter((request) =>
      request.url.endsWith('/workspaces/1/permissions/')
    )

  test('a created field refetches the workspace permissions', async () => {
    // A role on the table or database lists the fields it covers, and the
    // list was fetched before this field existed.
    const table = await workspaceWithTable()
    testApp.mock
      .onGet('/workspaces/1/permissions/')
      .reply(200, [{ name: 'core', permissions: ['refetched'] }])

    await store.dispatch('field/forceCreate', {
      table,
      values: { id: 1, table_id: 10, name: 'Go', type: 'text' },
    })
    await flushPromises()

    expect(store.getters['field/get'](1).name).toBe('Go')
    expect(store.getters['workspace/get'](1)._.permissions).toEqual([
      { name: 'core', permissions: ['refetched'] },
    ])
  })

  test('a restored field refetches the workspace permissions', async () => {
    const table = await workspaceWithTable()
    testApp.mock
      .onGet('/workspaces/1/permissions/')
      .reply(200, [{ name: 'core', permissions: ['refetched'] }])

    await store.dispatch('field/fieldRestored', {
      table,
      selectedView: null,
      values: { id: 1, table_id: 10, name: 'Go', type: 'text' },
    })
    await flushPromises()

    expect(store.getters['workspace/get'](1)._.permissions).toEqual([
      { name: 'core', permissions: ['refetched'] },
    ])
  })

  test('fields landing in a burst share one refetch and one follow-up', async () => {
    // An import creates many fields at once. One request runs, one more is
    // queued for whatever landed meanwhile, and the newest response is the
    // last applied.
    const table = await workspaceWithTable()
    testApp.mock.onGet('/workspaces/1/permissions/').reply(200, [])

    await Promise.all(
      [1, 2, 3].map((id) =>
        store.dispatch('field/forceCreate', {
          table,
          values: { id, table_id: 10, name: `Field ${id}`, type: 'text' },
        })
      )
    )
    await flushPromises()

    expect(permissionRequests()).toHaveLength(2)
  })

  test('a created field still shows when the permissions cannot be refetched', async () => {
    testApp.dontFailOnErrorResponses()
    const table = await workspaceWithTable()
    testApp.mock.onGet('/workspaces/1/permissions/').reply(500)

    await store.dispatch('field/forceCreate', {
      table,
      values: { id: 1, table_id: 10, name: 'Go', type: 'text' },
    })
    await flushPromises()

    expect(store.getters['field/get'](1).name).toBe('Go')
    expect(store.state.toast.permissionsUpdated).toBe(true)
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

  test('realtime error recovery requests primary-backed field data', async () => {
    await store.dispatch('field/forceSetFields', {
      fields: [
        {
          id: 1,
          table_id: 10,
          name: 'AI field',
          type: 'text',
          error: null,
        },
      ],
    })
    store.commit('field/SET_LOADED', { tableId: 10, viewId: null })
    let requestHeaders
    testApp.mock.onGet('/database/fields/table/10/').reply((config) => {
      requestHeaders = config.headers
      return [
        200,
        [
          {
            id: 1,
            table_id: 10,
            name: 'AI field',
            type: 'text',
            error: null,
          },
        ],
      ]
    })

    await store.dispatch('field/refreshLoadedFieldErrors', {
      realtimeRecovery: true,
    })

    expect(requestHeaders['X-Baserow-Realtime-Recovery']).toBe('true')
  })

  test('an older error refresh cannot overwrite a newer response', async () => {
    await store.dispatch('field/forceSetFields', {
      fields: [
        {
          id: 1,
          table_id: 10,
          name: 'AI field',
          type: 'text',
          error: null,
        },
      ],
    })
    store.commit('field/SET_LOADED', { tableId: 10, viewId: null })
    const resolvers = []
    testApp.mock.onGet('/database/fields/table/10/').reply(
      () =>
        new Promise((resolve) => {
          resolvers.push(resolve)
        })
    )

    const olderRefresh = store.dispatch('field/refreshLoadedFieldErrors')
    await vi.waitFor(() => expect(resolvers).toHaveLength(1))
    const newerRefresh = store.dispatch('field/refreshLoadedFieldErrors')
    await vi.waitFor(() => expect(resolvers).toHaveLength(2))

    resolvers[1]([
      200,
      [
        {
          id: 1,
          table_id: 10,
          name: 'AI field',
          type: 'text',
          error: 'New error',
        },
      ],
    ])
    await newerRefresh
    resolvers[0]([
      200,
      [
        {
          id: 1,
          table_id: 10,
          name: 'AI field',
          type: 'text',
          error: 'Old error',
        },
      ],
    ])
    await olderRefresh

    expect(store.getters['field/get'](1).error).toBe('New error')
  })
})
