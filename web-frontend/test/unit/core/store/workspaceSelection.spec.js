import { TestApp } from '@baserow/test/helpers/testApp'
import flushPromises from 'flush-promises'

describe('Workspace selection during bootstrap', () => {
  let testApp
  let store

  beforeEach(async () => {
    testApp = new TestApp()
    store = testApp.store
    for (const id of [1, 2]) {
      await store.dispatch('workspace/forceCreate', {
        id,
        name: `Workspace ${id}`,
        users: [],
      })
    }
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('keeps workspace actions loading until permissions arrive', async () => {
    let finishPermissions
    testApp.mock.onGet('/workspaces/1/permissions/').reply(
      () =>
        new Promise((resolve) => {
          finishPermissions = resolve
        })
    )
    const selection = store.dispatch('workspace/selectById', 1)
    await flushPromises()
    expect(store.getters['workspace/get'](1)._.additionalLoading).toBe(true)
    finishPermissions([200, {}])
    await selection
    expect(store.getters['workspace/get'](1)._.additionalLoading).toBe(false)
    expect(store.getters['workspace/getSelected'].id).toBe(1)
  })

  test('late permissions cannot switch back to a workspace already left', async () => {
    let finishFirst
    testApp.mock.onGet('/workspaces/1/permissions/').reply(
      () =>
        new Promise((resolve) => {
          finishFirst = resolve
        })
    )
    testApp.mock.onGet('/workspaces/2/permissions/').reply(200, {})
    const firstSelection = store.dispatch('workspace/selectById', 1)
    await flushPromises()
    await store.dispatch('workspace/selectById', 2)
    finishFirst([200, {}])
    await firstSelection
    expect(store.getters['workspace/getSelected'].id).toBe(2)
  })
})
