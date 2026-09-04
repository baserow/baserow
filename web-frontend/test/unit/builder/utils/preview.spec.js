import { describe, expect, test } from 'vitest'

import {
  getBuilderPreviewApiPath,
  getBuilderPreviewCookieName,
  getBuilderPreviewCookiePath,
  getBuilderPreviewIdFromApiUrl,
  getBuilderPreviewSsrCookieName,
  getBuilderPreviewUserSourceAuthConfig,
  getBuilderPreviewUserSourceCookieName,
} from '@baserow/modules/builder/utils/preview'

const config = { public: { baserowFrontendCookiePrefix: 'test_' } }

describe('builder preview cookies', () => {
  test('uses fixed names and builder-specific paths', () => {
    expect(getBuilderPreviewCookieName(config)).toBe(
      'test_baserow_builder_preview'
    )
    expect(getBuilderPreviewSsrCookieName(config)).toBe(
      'test_baserow_builder_preview_ssr'
    )
    expect(getBuilderPreviewUserSourceCookieName()).toBe(
      'baserow_builder_preview_user_source'
    )
    expect(getBuilderPreviewCookiePath(42)).toBe('/builder/preview/42')
  })

  test('uses and recognizes builder-scoped preview API paths', () => {
    expect(getBuilderPreviewApiPath(42, 'pages/7/elements/')).toBe(
      'builder/preview/42/pages/7/elements/'
    )
    expect(
      getBuilderPreviewIdFromApiUrl(
        'https://api.example.com/api/builder/preview/42/pages/7/elements/'
      )
    ).toBe(42)
    expect(
      getBuilderPreviewIdFromApiUrl(
        'builder/domains/published/page/7/elements/'
      )
    ).toBeNull()
  })

  test('provides core with generic user source authentication settings', () => {
    const builder = {
      id: 42,
      user_sources: [{ id: 10 }, { id: 11 }],
    }

    expect(
      getBuilderPreviewUserSourceAuthConfig(
        builder,
        'https://preview.example.com'
      )
    ).toEqual({
      authenticationUrls: {
        10: 'builder/preview/42/user-sources/10/token-auth/',
        11: 'builder/preview/42/user-sources/11/token-auth/',
      },
      refreshUrl: 'builder/preview/42/user-source-auth-refresh/',
      cookieName: 'baserow_builder_preview_user_source',
      cookieOptions: {
        cookieUrl: 'https://preview.example.com',
        path: '/builder/preview/42',
        sameSite: 'Lax',
      },
    })
  })
})
