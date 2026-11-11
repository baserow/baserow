import { loginAgainAfterPasswordChange } from '@baserow/modules/core/utils/auth'

function makeStore(loginResult) {
  return {
    getters: { 'auth/getUsername': 'admin@baserow.io' },
    // Lets the redirect to the login page finish straight away.
    app: { hooks: { hookOnce: (name, callback) => callback() } },
    dispatch: vi.fn((type) =>
      Promise.resolve(type === 'auth/login' ? loginResult : undefined)
    ),
  }
}

describe('loginAgainAfterPasswordChange', () => {
  test('signs the user back in with the new password', async () => {
    const store = makeStore({ id: 1, username: 'admin@baserow.io' })
    const router = { push: vi.fn() }

    const signedIn = await loginAgainAfterPasswordChange(
      router,
      store,
      'new-password'
    )

    expect(signedIn).toBe(true)
    expect(store.dispatch.mock.calls).toEqual([
      ['auth/login', { email: 'admin@baserow.io', password: 'new-password' }],
    ])
    expect(router.push).not.toHaveBeenCalled()
  })

  test('sends a user with two-factor auth to the login page with a message', async () => {
    const store = makeStore({ two_factor_auth: 'totp', token: 'challenge' })
    const router = { push: vi.fn() }

    const signedIn = await loginAgainAfterPasswordChange(
      router,
      store,
      'new-password'
    )

    expect(signedIn).toBe(false)
    expect(router.push).toHaveBeenCalledWith({
      name: 'login',
      query: { noredirect: null },
    })
    const dispatchedTypes = store.dispatch.mock.calls.map(([type]) => type)
    expect(dispatchedTypes).toContain('auth/forceLogoff')
    expect(store.dispatch).toHaveBeenCalledWith(
      'toast/setUserPasswordChanged',
      true
    )
  })
})
