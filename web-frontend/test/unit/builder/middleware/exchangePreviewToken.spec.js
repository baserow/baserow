import { beforeEach, describe, expect, test, vi } from 'vitest'

const { navigateTo, unsetToken, useNuxtApp, useRequestURL, useRuntimeConfig } =
  vi.hoisted(() => ({
    navigateTo: vi.fn(),
    unsetToken: vi.fn(),
    useNuxtApp: vi.fn(() => ({ app: true })),
    useRequestURL: vi.fn(),
    useRuntimeConfig: vi.fn(),
  }))

vi.mock('#imports', () => ({
  defineNuxtRouteMiddleware: vi.fn((middleware) => middleware),
  navigateTo,
  useNuxtApp,
  useRequestEvent: vi.fn(),
  useRequestURL,
  useRuntimeConfig,
}))

vi.mock('@baserow/modules/core/utils/auth', async (importOriginal) => ({
  ...(await importOriginal()),
  unsetToken,
}))

vi.mock('h3', () => ({
  appendResponseHeader: vi.fn(),
}))

const {
  default: exchangePreviewToken,
  canExchangePreviewTokenDuringSsr,
  getCleanPreviewUrl,
  getPreviewToken,
} = await import('@baserow/modules/builder/middleware/exchangePreviewToken')

beforeEach(() => {
  vi.clearAllMocks()
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
      'https://preview.example.com/page?foo=bar&preview_token=token'
    )

    expect(
      getCleanPreviewUrl(requestUrl, 'https://preview.example.com').toString()
    ).toBe('https://preview.example.com/page?foo=bar')
  })

  test('only exchanges during SSR when preview and backend share an origin', () => {
    const requestUrl = new URL('https://preview.example.com/page')

    expect(
      canExchangePreviewTokenDuringSsr(
        requestUrl,
        'https://preview.example.com'
      )
    ).toBe(true)
    expect(
      canExchangePreviewTokenDuringSsr(requestUrl, 'https://api.example.com')
    ).toBe(false)
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
    })

    await exchangePreviewToken({ query: { preview_token: 'new-token' } })

    expect(unsetToken).toHaveBeenCalledOnce()
    expect(unsetToken.mock.calls[0][1]).toBe('user_source_token')
  })
})
