import { getCookieName } from '@baserow/modules/core/utils/cookie'

describe('cookie utils', () => {
  test('getCookieName returns the default cookie name without a prefix', () => {
    expect(
      getCookieName(
        { public: { baserowFrontendCookiePrefix: '' } },
        'jwt_token'
      )
    ).toBe('jwt_token')
  })

  test('getCookieName prefixes cookies when configured', () => {
    expect(
      getCookieName(
        { public: { baserowFrontendCookiePrefix: 'baserow_4010_' } },
        'jwt_token'
      )
    ).toBe('baserow_4010_jwt_token')
  })
})
