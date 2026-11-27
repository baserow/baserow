import { OAuthAccountIntegrationType } from '@baserow/modules/integrations/oauthAccount/integrationTypes'

export const TEST_OAUTH_TYPE = 'test_oauth'

/** A provider that exists for the tests only. */
export class TestOAuthIntegrationType extends OAuthAccountIntegrationType {
  static getType() {
    return TEST_OAUTH_TYPE
  }

  get providerName() {
    return 'Example'
  }

  get image() {
    return ''
  }
}

/**
 * Register the test provider on a TestApp's registry.
 *
 * @returns {Function} Unregisters it.
 */
export function registerTestOAuthType(testApp) {
  const registry = testApp.getRegistry()
  const type = new TestOAuthIntegrationType({ app: testApp._app })
  registry.register('integration', type)
  return () => registry.unregister('integration', TEST_OAUTH_TYPE)
}
