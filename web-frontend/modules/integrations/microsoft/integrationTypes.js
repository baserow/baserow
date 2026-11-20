import { OAuthAccountIntegrationType } from '@baserow/modules/integrations/oauthAccount/integrationTypes'
import microsoftImage from '@baserow/modules/integrations/microsoft/assets/images/microsoft.svg?url'
import MicrosoftIntegrationForm from '@baserow/modules/integrations/microsoft/components/MicrosoftIntegrationForm'

/**
 * A Microsoft account, connected by signing in with Microsoft. Services act as
 * that account.
 */
export class MicrosoftIntegrationType extends OAuthAccountIntegrationType {
  static getType() {
    return 'microsoft'
  }

  get providerName() {
    return 'Microsoft'
  }

  get image() {
    return microsoftImage
  }

  get iconColor() {
    return 'darker-cyan'
  }

  get formComponent() {
    return MicrosoftIntegrationForm
  }

  getOrder() {
    return 11
  }
}
