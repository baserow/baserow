import { describe, test, expect, vi, beforeEach } from 'vitest'

import { impersonateMiddleware } from '@baserow/modules/core/middleware/impersonate'
import UserService from '@baserow/modules/core/services/admin/users'

vi.mock('@baserow/modules/core/services/admin/users', () => ({
  default: vi.fn(),
}))

/**
 * Builds a minimal `nuxtApp` stub backed by configurable store getters and a
 * spy-able `dispatch`. Mirrors the surface area the middleware actually uses.
 */
const buildNuxtApp = ({ isAuthenticated, userId } = {}) => {
  const dispatch = vi.fn()
  const getters = {
    'auth/isAuthenticated': !!isAuthenticated,
    'auth/getUserId': userId,
  }
  return {
    nuxtApp: {
      $store: { getters, dispatch },
      $client: {},
    },
    dispatch,
  }
}

describe('impersonate middleware', () => {
  let impersonate

  beforeEach(() => {
    impersonate = vi.fn().mockResolvedValue({
      data: { user: { id: 42 }, access_token: 'a', refresh_token: 'b' },
    })
    UserService.mockReturnValue({ impersonate })
  })

  test('does nothing when the __impersonate-user query param is missing', async () => {
    const { nuxtApp, dispatch } = buildNuxtApp({
      isAuthenticated: true,
      userId: 1,
    })

    await impersonateMiddleware({ query: {} }, { nuxtApp })

    expect(impersonate).not.toHaveBeenCalled()
    expect(dispatch).not.toHaveBeenCalled()
  })

  test('bails out when the user is not authenticated, even if the query param is set', async () => {
    const { nuxtApp, dispatch } = buildNuxtApp({
      isAuthenticated: false,
    })

    await impersonateMiddleware(
      { query: { '__impersonate-user': '5' } },
      { nuxtApp }
    )

    expect(impersonate).not.toHaveBeenCalled()
    expect(dispatch).not.toHaveBeenCalled()
  })

  test('bails out when the current user is already the impersonated user', async () => {
    const { nuxtApp, dispatch } = buildNuxtApp({
      isAuthenticated: true,
      userId: 5,
    })

    await impersonateMiddleware(
      { query: { '__impersonate-user': '5' } },
      { nuxtApp }
    )

    expect(impersonate).not.toHaveBeenCalled()
    expect(dispatch).not.toHaveBeenCalled()
  })

  test('matches when the store id is already a string equal to the query param', async () => {
    const { nuxtApp, dispatch } = buildNuxtApp({
      isAuthenticated: true,
      userId: '5',
    })

    await impersonateMiddleware(
      { query: { '__impersonate-user': '5' } },
      { nuxtApp }
    )

    expect(impersonate).not.toHaveBeenCalled()
    expect(dispatch).not.toHaveBeenCalled()
  })

  test('impersonates the user and updates the store when authenticated as a different user', async () => {
    const { nuxtApp, dispatch } = buildNuxtApp({
      isAuthenticated: true,
      userId: 1,
    })

    await impersonateMiddleware(
      { query: { '__impersonate-user': '5' } },
      { nuxtApp }
    )

    expect(impersonate).toHaveBeenCalledWith('5')
    expect(dispatch).toHaveBeenCalledWith('auth/forceSetUserData', {
      user: { id: 42 },
      access_token: 'a',
      refresh_token: 'b',
    })
    expect(dispatch).toHaveBeenCalledWith('auth/preventSetToken')
    expect(dispatch).toHaveBeenCalledWith(
      'impersonating/setImpersonating',
      true
    )
  })
})
