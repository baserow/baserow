import { describe, expect, test } from 'vitest'

import { prepareRequestHeaders } from '@baserow/modules/core/plugins/clientHandler'

const makeStore = (mode) => ({
  getters: {
    'userSourceUser/getCurrentApplication': null,
    'userSourceUser/getCurrentApplicationMode': mode,
    'userSourceUser/isAuthenticated': () => false,
    'userSourceUser/isRefreshing': () => false,
    'auth/isAuthenticated': false,
    'auth/webSocketId': null,
  },
})

const prepareConfig = (mode, usePreviewAuth, previewSsrAuth = {}) => {
  const prepareHeaders = prepareRequestHeaders(makeStore(mode), previewSsrAuth)
  return prepareHeaders({
    headers: {},
    usePreviewAuth,
    withCredentials: false,
  })
}

describe('preview request headers', () => {
  test('marks requests using preview authentication', () => {
    const config = prepareConfig('preview', true)

    expect(config.withCredentials).toBe(true)
    expect(config.headers['X-Baserow-Builder-Preview']).toBe('true')
  })

  test('does not mark preview requests which do not use preview authentication', () => {
    const config = prepareConfig('preview', false)

    expect(config.withCredentials).toBe(false)
    expect(config.headers).not.toHaveProperty('X-Baserow-Builder-Preview')
  })

  test('does not mark public requests even when the service supports preview auth', () => {
    const config = prepareConfig('public', true)

    expect(config.withCredentials).toBe(false)
    expect(config.headers).not.toHaveProperty('X-Baserow-Builder-Preview')
  })

  test('forwards only the companion credential for preview-auth SSR requests', () => {
    const previewSsrAuth = {
      backendCookieName: 'test_baserow_builder_preview',
      session: 'signed-session',
    }

    const previewConfig = prepareConfig('preview', true, previewSsrAuth)
    const unmarkedConfig = prepareConfig('preview', false, previewSsrAuth)
    const publicConfig = prepareConfig('public', true, previewSsrAuth)

    expect(previewConfig.headers.Cookie).toBe(
      'test_baserow_builder_preview=signed-session'
    )
    expect(unmarkedConfig.headers).not.toHaveProperty('Cookie')
    expect(publicConfig.headers).not.toHaveProperty('Cookie')
  })
})
