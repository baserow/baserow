import { describe, expect, test } from 'vitest'

import { prepareRequestHeaders } from '@baserow/modules/core/plugins/clientHandler'
import { prepareUserSourceRequestHeaders } from '@baserow/modules/core/plugins/userSourceClientHandler'
import { prepareBuilderPreviewRequest } from '@baserow/modules/builder/plugins/previewClientHandler'

const makeStore = (getterOverrides = {}) => ({
  getters: {
    'userSourceUser/getCurrentApplication': null,
    'userSourceUser/isAuthenticated': () => false,
    'userSourceUser/isRefreshing': () => false,
    'auth/isAuthenticated': false,
    'auth/webSocketId': null,
    ...getterOverrides,
  },
})

const prepareConfig = (url, previewSsrAuth = {}, getterOverrides = {}) => {
  const store = makeStore(getterOverrides)
  let config = {
    headers: {},
    url,
    withCredentials: false,
  }

  // Axios executes request interceptors in reverse registration order.
  config = prepareBuilderPreviewRequest(previewSsrAuth)(config)
  config = prepareUserSourceRequestHeaders(store)(config)
  return prepareRequestHeaders(store)(config)
}

describe('builder preview request headers', () => {
  test('sends credentials for builder preview API URLs', () => {
    const config = prepareConfig('builder/preview/123/pages/456/elements/')

    expect(config.withCredentials).toBe(true)
  })

  test('does not mark published URLs', () => {
    const config = prepareConfig('builder/domains/published/page/456/elements/')

    expect(config.withCredentials).toBe(false)
  })

  test('keeps user source authentication secondary on preview URLs', () => {
    const application = { id: 123 }
    const config = prepareConfig(
      'builder/preview/123/data-sources/456/dispatch/',
      {},
      {
        'userSourceUser/getCurrentApplication': application,
        'userSourceUser/isAuthenticated': () => true,
        'userSourceUser/accessToken': () => 'user-source-token',
        'auth/isAuthenticated': true,
        'auth/token': 'editor-token',
      }
    )

    expect(config.withCredentials).toBe(true)
    expect(config.headers.Authorization).toBe('JWT user-source-token')
    expect(config.headers).not.toHaveProperty('UserSourceAuthorization')
    expect(config.headers).not.toHaveProperty('ClientSessionId')
  })

  test('keeps both authentication contexts on non-preview URLs', () => {
    const application = { id: 123 }
    const config = prepareConfig(
      'builder/domains/published/page/456/elements/',
      {},
      {
        'userSourceUser/getCurrentApplication': application,
        'userSourceUser/isAuthenticated': () => true,
        'userSourceUser/accessToken': () => 'user-source-token',
        'auth/isAuthenticated': true,
        'auth/token': 'editor-token',
        'auth/getUntrustedClientSessionId': 'client-session',
      }
    )

    expect(config.headers.Authorization).toBe('JWT editor-token')
    expect(config.headers.UserSourceAuthorization).toBe('JWT user-source-token')
    expect(config.headers.ClientSessionId).toBe('client-session')
  })

  test('forwards only the companion credential for preview-auth SSR requests', () => {
    const previewSsrAuth = {
      backendCookieName: 'test_baserow_builder_preview',
      session: 'signed-session',
    }

    const previewUrl = 'builder/preview/123/pages/456/elements/'
    const previewConfig = prepareConfig(previewUrl, previewSsrAuth)
    const unmarkedConfig = prepareConfig(
      'builder/domains/published/page/456/elements/',
      previewSsrAuth
    )

    expect(previewConfig.headers.Cookie).toBe(
      'test_baserow_builder_preview=signed-session'
    )
    expect(unmarkedConfig.headers).not.toHaveProperty('Cookie')
  })
})
