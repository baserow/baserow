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
})
