import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import OAuthAccountForm from '@baserow/modules/integrations/oauthAccount/components/OAuthAccountForm'

/**
 * An integration that holds one person's account at a provider, connected by
 * signing in with the provider in a popup. Services act as that account. A
 * provider extends it, gives its `providerName`, `name`, `image`, and may give
 * a form of its own that wraps `OAuthAccountForm` to add fields in its slot.
 */
export class OAuthAccountIntegrationType extends IntegrationType {
  /** The provider's name, as on its sign-in button, e.g. `Microsoft`. */
  get providerName() {
    throw new Error('The providerName of an OAuth account type must be set.')
  }

  get name() {
    return this.providerName
  }

  /**
   * Whether the form offers to sign in. By default only when the
   * installation has an OAuth app for the provider; a provider that lets an
   * integration bring its own app also says yes when this one has it.
   *
   * @param {Object} config What the config endpoint answered.
   * @param {Object} integration The integration, empty when creating one.
   * @returns {boolean}
   */
  canSignIn(config, integration) {
    return Boolean(config?.configured)
  }

  /**
   * The scopes a service needs that the integration's account hasn't granted,
   * to offer "Grant access". Compared with the integration as the store holds
   * it, so it's current as soon as someone grants access. The backend writes
   * both lists, normalized the same way, and checks again at dispatch.
   *
   * @param {Object} integration The integration, from the store.
   * @param {Object} service The service, with its `required_scopes`.
   * @returns {string[]} Empty when it isn't connected: it must sign in first.
   */
  getMissingScopes(integration, service) {
    if (!integration?.connected) return []
    const granted = new Set(
      (integration.scopes || []).map((scope) => scope.toLowerCase())
    )
    return (service?.required_scopes || []).filter(
      (scope) => !granted.has(scope.toLowerCase())
    )
  }

  getSummary(integration) {
    const account = integration.account_email || integration.account_name
    if (!account) {
      return this.app.$i18n.t(
        'oauthAccountIntegrationType.notConnectedSummary',
        {
          provider: this.providerName,
        }
      )
    }
    return this.app.$i18n.t('oauthAccountIntegrationType.summary', {
      provider: this.providerName,
      email: account,
    })
  }

  getErrorMessage(integration) {
    if (!integration.connected) {
      return this.app.$i18n.t('oauthAccountIntegrationType.errorNotConnected', {
        provider: this.providerName,
      })
    }
    return super.getErrorMessage(integration)
  }

  get formComponent() {
    return OAuthAccountForm
  }

  /**
   * The account form needs this type, even when the provider's own form saves
   * the integration before anyone signs in.
   */
  getFormProps(context) {
    return {
      ...super.getFormProps(context),
      integrationType: this,
      serviceTypes: context.serviceTypes,
    }
  }

  /** The sign-in creates the integration, not the modal's create button. */
  get createsItself() {
    return true
  }

  getDefaultValues() {
    // Left empty, the integration is named after the account that signs in,
    // which tells several integrations of one provider apart.
    return { name: '' }
  }
}
