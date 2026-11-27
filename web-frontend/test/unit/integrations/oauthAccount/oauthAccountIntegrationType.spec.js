import { TestApp } from '@baserow/test/helpers/testApp'
import {
  TEST_OAUTH_TYPE,
  registerTestOAuthType,
} from '@baserow/test/unit/integrations/oauthAccount/testIntegrationType'

describe('OAuthAccountIntegrationType', () => {
  let testApp = null
  let unregister = null

  beforeEach(() => {
    testApp = new TestApp()
    unregister = registerTestOAuthType(testApp)
  })

  afterEach(async () => {
    unregister()
    await testApp.afterEach()
  })

  const integrationType = () =>
    testApp.getRegistry().get('integration', TEST_OAUTH_TYPE)

  test('creates its integration from its own form', () => {
    expect(integrationType().createsItself).toBe(true)
    expect(integrationType().name).toBe('Example')
    // An empty name lets the backend name it after the account.
    expect(integrationType().getDefaultValues()).toEqual({ name: '' })
  })

  test('summarises the account and says when it must reconnect', () => {
    const type = integrationType()

    expect(
      type.getSummary({ connected: true, account_email: 'alice@example.com' })
    ).toBe('oauthAccountIntegrationType.summary')
    expect(type.getSummary({ connected: false, account_email: '' })).toBe(
      'oauthAccountIntegrationType.notConnectedSummary'
    )
    expect(
      type.getErrorMessage({ connected: true, account_email: 'a@b.c' })
    ).toBeNull()
    expect(
      type.getErrorMessage({ connected: false, account_email: 'a@b.c' })
    ).toBe('oauthAccountIntegrationType.errorNotConnected')
  })

  test('an account known by its name only is connected', () => {
    expect(
      integrationType().getSummary({ connected: true, account_name: 'Alice' })
    ).toBe('oauthAccountIntegrationType.summary')
  })

  test('offers to sign in when the installation has an app', () => {
    const type = integrationType()

    expect(type.canSignIn({ configured: true }, {})).toBe(true)
    expect(type.canSignIn({ configured: false }, {})).toBe(false)
    expect(type.canSignIn(null, {})).toBe(false)
  })

  test('says which scopes a service still needs from the live integration', () => {
    const type = integrationType()
    const service = { required_scopes: ['Messages.Send', 'Chat.Read'] }

    expect(
      type.getMissingScopes(
        { connected: true, scopes: ['openid', 'messages.send'] },
        service
      )
    ).toEqual(['Chat.Read'])
    expect(
      type.getMissingScopes(
        { connected: true, scopes: ['Messages.Send', 'Chat.Read'] },
        service
      )
    ).toEqual([])
    // Not connected: it signs in first, which asks for them.
    expect(
      type.getMissingScopes({ connected: false, scopes: [] }, service)
    ).toEqual([])
    expect(type.getMissingScopes(null, service)).toEqual([])
    expect(type.getMissingScopes({ connected: true, scopes: [] }, {})).toEqual(
      []
    )
  })
})
