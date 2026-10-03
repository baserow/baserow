import { describe, expect, test } from 'vitest'

describe('Enterprise app auth provider callback errors', () => {
  test('SAML returns the translated error for its user source and ignores others', () => {
    const testApp = useNuxtApp()
    const samlType = testApp.$registry.get('appAuthProvider', 'saml')

    const url = new URL(
      'https://site.example/?saml_error__42=errorApplicationUserLimitReached'
    )

    expect(samlType.getAuthProviderCallback({ id: 42 }, url)).toEqual({
      sourceId: 42,
      token: null,
      error: { message: 'loginError.errorApplicationUserLimitReached' },
      queryParamNames: ['saml_error__42'],
    })
    expect(samlType.getAuthProviderCallback({ id: 99 }, url)).toBeNull()
    expect(
      samlType.getAuthProviderCallback(
        { id: 42 },
        new URL('https://site.example/')
      )
    ).toBeNull()
  })

  test('OIDC returns the translated error from its own error parameter', () => {
    const testApp = useNuxtApp()
    const oidcType = testApp.$registry.get('appAuthProvider', 'openid_connect')

    const url = new URL(
      'https://site.example/?oidc_error__7=errorApplicationUserLimitReached'
    )

    expect(oidcType.getAuthProviderCallback({ id: 7 }, url)).toEqual({
      sourceId: 7,
      token: null,
      error: { message: 'loginError.errorApplicationUserLimitReached' },
      queryParamNames: ['oidc_error__7'],
    })
    expect(
      oidcType.getAuthProviderCallback(
        { id: 7 },
        new URL(
          'https://site.example/?saml_error__7=errorApplicationUserLimitReached'
        )
      )
    ).toBeNull()
  })
})

describe('Builder auth provider callback methods', () => {
  test.each([
    ['saml', 'user_source_saml_token__12', 'saml_error__12'],
    ['openid_connect', 'user_source_oidc_token__12', 'oidc_error__12'],
  ])(
    '%s owns its callback parsing',
    (providerType, queryParamName, errorParamName) => {
      const provider = useNuxtApp().$registry.get(
        'appAuthProvider',
        providerType
      )
      const callbackUrl = new URL(
        `https://site.example/?${queryParamName}=refresh&${errorParamName}=error&unknown=value`
      )

      expect(
        provider.getAuthProviderCallbackQueryParamNames(callbackUrl)
      ).toEqual([queryParamName])

      expect(
        provider.getAuthProviderCallback(
          { id: 12 },
          new URL(`https://site.example/?${queryParamName}=refresh`)
        )
      ).toEqual({
        sourceId: 12,
        token: 'refresh',
        error: null,
        queryParamNames: [queryParamName],
      })
      expect(
        provider.getAuthProviderCallback(
          { id: 12 },
          new URL(`https://site.example/?${queryParamName}=`)
        )
      ).toBeNull()
      expect(
        provider.getAuthProviderCallback(
          { id: 12 },
          new URL(
            `https://site.example/?${queryParamName}=refresh&${errorParamName}=error`
          )
        )
      ).toBeNull()
    }
  )
})
