import { afterEach, beforeEach, describe, expect, test } from 'vitest'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Application realtime updates', () => {
  let testApp, application

  beforeEach(async () => {
    testApp = new TestApp()
    application = await testApp.store.dispatch('application/forceCreate', {
      id: 1,
      type: 'agent',
      name: 'Support agent',
      readiness: 'ready',
      workspace: { id: 1 },
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('tracks every external update while preserving the application object', async () => {
    expect(application._.realtimeVersion).toBe(0)
    expect(application._.viaRealtime).toBe(false)

    for (let version = 1; version <= 2; version++) {
      await testApp.store.dispatch('application/forceUpdate', {
        application,
        data: { readiness: 'ready' },
        viaRealtime: true,
      })

      expect(testApp.store.getters['application/get'](1)).toBe(application)
      expect(application._.realtimeVersion).toBe(version)
      expect(application._.viaRealtime).toBe(true)
    }
  })

  test('local metadata updates do not advance the external version', async () => {
    await testApp.store.dispatch('application/forceUpdate', {
      application,
      data: { readiness: 'ready' },
      viaRealtime: true,
    })
    await testApp.store.dispatch('application/forceUpdate', {
      application,
      data: { last_viewed: '2026-10-22T12:00:00Z' },
    })

    expect(application.last_viewed).toBe('2026-10-22T12:00:00Z')
    expect(application._.realtimeVersion).toBe(1)
    expect(application._.viaRealtime).toBe(false)
  })
})

describe('Shared application', () => {
  let testApp, store

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    await store.dispatch('application/forceSetAll', {
      applications: [
        {
          id: 1,
          type: 'database',
          name: 'Database',
          order: 1,
          workspace: { id: 1 },
          tables: [],
        },
        {
          id: 2,
          type: 'shared',
          name: '__shared__',
          order: 0,
          workspace: { id: 1 },
        },
        {
          id: 3,
          type: 'shared',
          name: '__shared__',
          order: 0,
          workspace: { id: 2 },
        },
      ],
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  const idsOf = (applications) => applications.map(({ id }) => id)
  const sharedOf = (workspaceId) =>
    store.getters['application/getSharedApplication']({ id: workspaceId })

  test('is left out of the application lists', () => {
    const ofWorkspace = (id) =>
      idsOf(store.getters['application/getAllOfWorkspace']({ id }))

    expect(idsOf(store.getters['application/getAll'])).toEqual([1])
    expect(ofWorkspace(1)).toEqual([1])
    expect(ofWorkspace(2)).toEqual([])
  })

  test('is returned per workspace and by id', () => {
    expect(sharedOf(1).id).toBe(2)
    expect(sharedOf(2).id).toBe(3)
    expect(sharedOf(3)).toBeUndefined()
    expect(store.getters['application/get'](2)).toBe(sharedOf(1))
  })

  test('is returned from the store without a request', async () => {
    // The mock adapter throws on any request without a handler.
    const shared = await store.dispatch('application/fetchSharedApplication', {
      id: 1,
    })

    expect(shared).toBe(sharedOf(1))
  })

  test('is fetched with the applications of its workspace when missing', async () => {
    testApp.mock.onGet('/applications/workspace/4/').replyOnce(200, [
      {
        id: 5,
        type: 'database',
        name: 'Database',
        order: 1,
        workspace: { id: 4 },
        tables: [],
      },
      {
        id: 6,
        type: 'shared',
        name: '__shared__',
        order: 0,
        workspace: { id: 4 },
      },
    ])

    const shared = await store.dispatch('application/fetchSharedApplication', {
      id: 4,
    })

    expect(shared.id).toBe(6)
    expect(sharedOf(4)).toBe(shared)
    // Only the shared application is added, the others are left as they were.
    expect(store.getters['application/get'](5)).toBeUndefined()
  })

  test('holds the workspace integrations', async () => {
    const shared = sharedOf(1)
    expect(shared.integrations).toEqual([])

    await store.dispatch('integration/forceCreate', {
      application: shared,
      integration: { id: 10, type: 'local_baserow', name: 'Shared' },
    })

    const integrations = store.getters['integration/getIntegrations'](shared)
    expect(idsOf(integrations)).toEqual([10])
  })
})
