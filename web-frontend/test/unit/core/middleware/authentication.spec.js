import { describe, test, expect, vi, beforeEach } from 'vitest'
import { mockNuxtImport } from '@nuxt/test-utils/runtime'

import authenticationMiddleware from '@baserow/modules/core/middleware/authentication'
import {
  getTokenIfEnoughTimeLeft,
  setToken,
  setUserSessionCookie,
} from '@baserow/modules/core/utils/auth'

const { store } = vi.hoisted(() => ({ store: { current: null } }))
// Nuxt itself also calls useNuxtApp, so only the store is swapped.
mockNuxtImport('useNuxtApp', (original) => () => {
  const nuxtApp = original()
  return store.current ? { ...nuxtApp, $store: store.current } : nuxtApp
})

vi.mock('@baserow/modules/core/utils/auth', async (importOriginal) => ({
  ...(await importOriginal()),
  getTokenIfEnoughTimeLeft: vi.fn(),
  setToken: vi.fn(),
  setUserSessionCookie: vi.fn(),
}))

const encode = (value) =>
  btoa(JSON.stringify(value))
    .replace(/=+$/, '')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')

const buildToken = (claims) =>
  `${encode({ alg: 'HS256', typ: 'JWT' })}.${encode(claims)}.signature`

const buildStore = () => {
  const dispatch = vi.fn().mockResolvedValue()
  store.current = { getters: { 'auth/isAuthenticated': false }, dispatch }
  return { dispatch }
}

describe('authentication middleware', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test('uses the cookie token when the query token is of the same session', async () => {
    const { dispatch } = buildStore()
    const queryToken = buildToken({ jti: 'first' })
    const cookieToken = buildToken({ jti: 'second', session_id: 'first' })
    getTokenIfEnoughTimeLeft.mockResolvedValue(cookieToken)

    await authenticationMiddleware({
      query: { token: queryToken, user_session: 'signed' },
    })

    expect(dispatch).toHaveBeenCalledWith('auth/refresh', cookieToken)
    expect(setToken).not.toHaveBeenCalled()
    expect(setUserSessionCookie).not.toHaveBeenCalled()
  })

  test('uses the query token when it is of another session', async () => {
    const { dispatch } = buildStore()
    const queryToken = buildToken({ jti: 'other' })
    getTokenIfEnoughTimeLeft.mockResolvedValue(
      buildToken({ jti: 'second', session_id: 'first' })
    )

    await authenticationMiddleware({
      query: { token: queryToken, user_session: 'signed' },
    })

    expect(dispatch).toHaveBeenCalledWith('auth/refresh', queryToken)
    expect(setToken).toHaveBeenCalledWith(expect.anything(), queryToken)
    expect(setUserSessionCookie).toHaveBeenCalledWith(
      expect.anything(),
      'signed'
    )
  })

  test('uses the cookie token without a query token', async () => {
    const { dispatch } = buildStore()
    const cookieToken = buildToken({ jti: 'first' })
    getTokenIfEnoughTimeLeft.mockResolvedValue(cookieToken)

    await authenticationMiddleware({ query: {} })

    expect(dispatch).toHaveBeenCalledWith('auth/refresh', cookieToken)
    expect(setToken).not.toHaveBeenCalled()
    expect(setUserSessionCookie).not.toHaveBeenCalled()
  })
})
