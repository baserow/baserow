import { OAuthAccountIntegrationType } from '@baserow/modules/integrations/oauthAccount/integrationTypes'
import GoogleForm from '@baserow/modules/integrations/google/components/GoogleForm'

export class GoogleIntegrationType extends OAuthAccountIntegrationType {
  static getType() {
    return 'google'
  }
  get providerName() {
    return 'Google'
  }
  get iconClass() {
    return 'iconoir-google'
  }
  get formComponent() {
    return GoogleForm
  }
  // Custom clients must be saved before the shared flow can use them.
  get createsItself() {
    return false
  }
  getDefaultValues() {
    return { name: '', client_mode: 'custom', client_id: '' }
  }
  canSignIn(config, integration) {
    return integration?.client_mode === 'custom'
      ? Boolean(
          integration.id &&
          integration.client_id &&
          integration.has_client_secret
        )
      : super.canSignIn(config, integration)
  }
}
