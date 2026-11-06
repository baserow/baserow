import { describe, expect, test } from 'vitest'
import { createStore } from 'vuex'
import { Registry } from '@baserow/modules/core/registry'
import registerCore from '@baserow/modules/core/plugin'
import applicationStore from '@baserow/modules/core/store/application'

/** Minimal startup context, independent of TestApp's eagerly loaded fixtures. */
function makeApp(isAuthenticationPage) {
  return {
    $registry: new Registry(),
    $store: createStore({ modules: { application: applicationStore } }),
    $i18n: { t: (key) => key },
    $isApplicationShell: false,
    $isAuthenticationPage: isAuthenticationPage,
  }
}

describe('authentication startup', () => {
  test('sign-in registers password authentication without application features', async () => {
    const app = makeApp(true)
    await registerCore(app)
    expect(app.$registry.get('authProvider', 'password').getType()).toBe(
      'password'
    )
    expect(app.$registry.getAll('application')).toEqual({})
    expect(app.$registry.getAll('view')).toEqual({})
    expect(app.$registry.getAll('field')).toEqual({})
    expect(app.$store.hasModule('field')).toBe(false)
  })

  test('published runtime does not register administrator authentication providers', async () => {
    const app = makeApp(false)
    await registerCore(app)
    expect(app.$registry.getAll('authProvider')).toEqual({})
  })
})
