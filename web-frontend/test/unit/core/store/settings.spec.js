import { vi } from 'vitest'

import settingsStore from '@baserow/modules/core/store/settings'
import { TestApp } from '@baserow/test/helpers/testApp'

describe('Settings store', () => {
  let testApp = null
  let store = null

  beforeEach(() => {
    testApp = new TestApp()
    store = testApp.createStore({
      modules: { settings: settingsStore },
    })
  })

  afterEach(async () => {
    await testApp.afterEach()
  })

  test('an older settings request cannot overwrite a newer response', async () => {
    const resolvers = []
    testApp.mock.onGet('/settings/').reply(
      () =>
        new Promise((resolve) => {
          resolvers.push(resolve)
        })
    )

    const olderLoad = store.dispatch('settings/load')
    await vi.waitFor(() => expect(resolvers).toHaveLength(1))
    const newerLoad = store.dispatch('settings/load')
    await vi.waitFor(() => expect(resolvers).toHaveLength(2))

    resolvers[1]([200, { allow_new_signups: true }])
    await newerLoad
    resolvers[0]([200, { allow_new_signups: false }])
    await olderLoad

    expect(store.getters['settings/get']).toEqual({ allow_new_signups: true })
  })
})
