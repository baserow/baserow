describe('Enterprise app auth provider types getLoginError', () => {
  test('SAML returns the translated error for its user source and ignores others', () => {
    const testApp = useNuxtApp()
    const samlType = testApp.$registry.get('appAuthProvider', 'saml')

    const route = {
      query: { saml_error__42: 'errorApplicationUserLimitReached' },
    }

    // The i18n mock returns the key, which proves the right message is looked up.
    expect(samlType.getLoginError({ id: 42 }, route)).toBe(
      'loginError.errorApplicationUserLimitReached'
    )
    // The error belongs to another user source, so nothing is returned here.
    expect(samlType.getLoginError({ id: 99 }, route)).toBeNull()
    // No error parameter at all.
    expect(samlType.getLoginError({ id: 42 }, { query: {} })).toBeNull()
  })

  test('OIDC returns the translated error from its own error parameter', () => {
    const testApp = useNuxtApp()
    const oidcType = testApp.$registry.get('appAuthProvider', 'openid_connect')

    const route = {
      query: { oidc_error__7: 'errorApplicationUserLimitReached' },
    }

    expect(oidcType.getLoginError({ id: 7 }, route)).toBe(
      'loginError.errorApplicationUserLimitReached'
    )
    // OIDC must not react to the SAML error parameter.
    expect(
      oidcType.getLoginError(
        { id: 7 },
        { query: { saml_error__7: 'errorApplicationUserLimitReached' } }
      )
    ).toBeNull()
  })
})
