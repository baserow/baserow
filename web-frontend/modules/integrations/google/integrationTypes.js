import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import GoogleForm from '@baserow/modules/integrations/google/components/integrations/GoogleForm'

export class GoogleIntegrationType extends IntegrationType {
  static getType() {
    return 'google'
  }

  get name() {
    return this.app.$i18n.t('integrationType.google')
  }

  get iconClass() {
    return 'iconoir-google'
  }

  get iconColor() {
    return 'muted-red'
  }

  getSummary(integration) {
    if (!integration.has_refresh_token) {
      return this.app.$i18n.t('googleIntegrationType.notConnected')
    }
    return this.app.$i18n.t('googleIntegrationType.connectedAs', {
      account: integration.account_email || '…',
    })
  }

  get formComponent() {
    return GoogleForm
  }

  getDefaultValues() {
    return { client_id: '' }
  }

  getOrder() {
    return 30
  }
}
