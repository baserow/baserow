import { beforeEach, describe, expect, test, vi } from 'vitest'

const {
  navigateTo,
  previewCookie,
  unsetToken,
  useCookie,
  useNuxtApp,
  useRequestURL,
  useRuntimeConfig,
} = vi.hoisted(() => ({
  navigateTo: vi.fn(),
  previewCookie: { value: null },
  unsetToken: vi.fn(),
  useCookie: vi.fn(),
  useNuxtApp: vi.fn(() => ({
    app: true,
    $i18n: { t: (key) => key },
  })),
  useRequestURL: vi.fn(),
  useRuntimeConfig: vi.fn(),
}))

vi.mock('#imports', () => ({
  defineNuxtRouteMiddleware: vi.fn((middleware) => middleware),
  navigateTo,
  useCookie,
  useNuxtApp,
  useRequestURL,
  useRuntimeConfig,
}))

vi.mock('@baserow/modules/core/utils/auth', async (importOriginal) => ({
  ...(await importOriginal()),
  unsetToken,
}))

const {
  default: exchangePreviewToken,
  exchangePreviewHandoff,
  getCleanPreviewUrl,
  getPreviewHandoff,
  getPreviewToken,
  setPreviewHandoffCookie,
} = await import('@baserow/modules/builder/middleware/exchangePreviewToken')

beforeEach(() => {
  vi.clearAllMocks()
  previewCookie.value = null
  useCookie.mockReturnValue(previewCookie)
})

describe('exchangePreviewToken middleware helpers', () => {
  test('gets the preview token from the request URL first', () => {
    const requestUrl = new URL(
      'https://preview.example.com/page?preview_token=url-token'
    )
    const to = { query: { preview_token: 'route-token' } }

    expect(getPreviewToken(to, requestUrl)).toBe('url-token')
  })

  test('gets the preview token from the route query fallback', () => {
    const requestUrl = new URL('https://preview.example.com/page')
    const to = { query: { preview_token: ['route-token'] } }

    expect(getPreviewToken(to, requestUrl)).toBe('route-token')
  })

  test('removes the preview token from the clean preview URL', () => {
    const requestUrl = new URL(
      'https://preview.example.com/page?foo=bar&preview_token=token&preview_handoff=handoff'
    )

    expect(
      getCleanPreviewUrl(requestUrl, 'https://preview.example.com').toString()
    ).toBe('https://preview.example.com/page?foo=bar')
  })

  test('gets the preview handoff from the request URL', () => {
    const requestUrl = new URL(
      'https://preview.example.com/page?preview_handoff=handoff-code'
    )

    expect(getPreviewHandoff({ query: {} }, requestUrl)).toBe('handoff-code')
  })

  test('exchanges a handoff through the private backend and sets the SSR cookie', async () => {
    const config = {
      privateBackendUrl: 'http://backend:8000/',
      public: {
        baserowFrontendCookiePrefix: 'test_',
        builderPreviewUrl: 'https://preview.example.com',
      },
    }
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        preview_session: 'signed-session',
        expires_in: 1234,
        builder_id: 42,
      }),
    })

    const previewSession = await exchangePreviewHandoff(
      'handoff-code',
      42,
      config,
      fetch
    )
    setPreviewHandoffCookie(42, config, previewSession, useCookie)

    expect(fetch).toHaveBeenCalledWith(
      'http://backend:8000/api/builder/preview/handoff/',
      {
        method: 'POST',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          preview_handoff: 'handoff-code',
          builder_id: 42,
        }),
      }
    )
    expect(useCookie).toHaveBeenCalledWith('test_baserow_builder_preview_ssr', {
      httpOnly: true,
      maxAge: 1234,
      path: '/builder/preview/42',
      sameSite: 'lax',
      secure: true,
    })
    expect(previewCookie.value).toBe('signed-session')
  })

  test('clears the previous user-source session before exchanging a token', async () => {
    useRequestURL.mockReturnValue(
      new URL('https://preview.example.com/page?preview_token=new-token')
    )
    useRuntimeConfig.mockReturnValue({
      public: {
        builderPreviewUrl: 'https://preview.example.com',
        publicBackendUrl: 'https://api.example.com',
      },
      privateBackendUrl: 'http://backend:8000',
    })

    await exchangePreviewToken({
      query: { preview_token: 'new-token' },
      params: { builderId: '42' },
    })

    expect(unsetToken).toHaveBeenCalledOnce()
    expect(unsetToken.mock.calls[0][1]).toBe(
      'baserow_builder_preview_user_source'
    )
    expect(unsetToken.mock.calls[0][2]).toEqual({
      path: '/builder/preview/42',
    })
  })
})
