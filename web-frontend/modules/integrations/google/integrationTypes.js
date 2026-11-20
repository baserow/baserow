import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import GoogleForm from '@baserow/modules/integrations/google/components/GoogleForm'

export class GoogleIntegrationType extends IntegrationType {
  static getType() {
    return 'google'
  }
  get name() {
    return this.app.$i18n.t('googleIntegration.name')
  }
  get iconClass() {
    return 'iconoir-google'
  }
  get formComponent() {
    return GoogleForm
  }
  getSummary(integration) {
    return integration.connected
      ? integration.account_email
      : this.app.$i18n.t('googleIntegration.disconnected')
  }
  getDefaultValues() {
    return { client_mode: 'custom', client_id: '' }
  }
}
