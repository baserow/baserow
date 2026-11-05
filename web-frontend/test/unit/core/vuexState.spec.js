import { expect, test } from 'vitest'
import { createStore } from 'vuex'
import registerVuexState from '@baserow/modules/core/plugins/vuexState'

test('preserves SSR module state and initializes features first opened after hydration', async () => {
  const store = createStore({})
  const app = { $store: store, payload: { vuex: { shared: { value: 'SSR' } } } }
  await registerVuexState(app)
  const module = {
    namespaced: true,
    state: () => ({ value: 'fresh' }),
    mutations: {
      SET_VALUE(state, value) {
        state.value = value
      },
    },
  }
  store.registerModuleNuxtSafe('shared', module)
  expect(store.state.shared.value).toBe('SSR')

  store.registerModuleNuxtSafe('lateFeature', module)
  expect(store.state.lateFeature.value).toBe('fresh')
  store.commit('lateFeature/SET_VALUE', 'opened')
  expect(store.state.lateFeature.value).toBe('opened')
  expect(store.state.shared.value).toBe('SSR')
})
