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

  test('realtime AI features merge without replacing other settings', async () => {
    store.commit('settings/SET_SETTINGS', {
      allow_new_signups: true,
      kuma: { is_enabled: true },
    })

    await store.dispatch('settings/forceUpdateAIFeatures', {
      kuma: { is_enabled: false },
    })

    expect(store.getters['settings/get']).toEqual({
      allow_new_signups: true,
      kuma: { is_enabled: false },
    })
  })

  test('a realtime recovery load requests primary-backed data', async () => {
    let requestHeaders
    testApp.mock.onGet('/settings/').reply((config) => {
      requestHeaders = config.headers
      return [200, { allow_new_signups: true }]
    })

    await store.dispatch('settings/load', { realtimeRecovery: true })

    expect(requestHeaders['X-Baserow-Realtime-Recovery']).toBe('true')
  })

  test('a settings load cannot overwrite newer realtime AI features', async () => {
    let resolveLoad
    testApp.mock.onGet('/settings/').reply(
      () =>
        new Promise((resolve) => {
          resolveLoad = resolve
        })
    )

    const load = store.dispatch('settings/load')
    await vi.waitFor(() => expect(resolveLoad).toBeTypeOf('function'))

    await store.dispatch('settings/forceUpdateAIFeatures', {
      kuma: { is_enabled: true },
    })
    resolveLoad([
      200,
      {
        allow_new_signups: true,
        kuma: { is_enabled: false },
      },
    ])
    await load

    expect(store.getters['settings/get']).toEqual({
      allow_new_signups: true,
      kuma: { is_enabled: true },
    })
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
