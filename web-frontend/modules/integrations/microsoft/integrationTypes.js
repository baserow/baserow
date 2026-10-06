import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import MicrosoftForm from '@baserow/modules/integrations/microsoft/components/integrations/MicrosoftForm'

export class MicrosoftIntegrationType extends IntegrationType {
  static getType() {
    return 'microsoft'
  }

  get name() {
    return this.app.$i18n.t('integrationType.microsoft')
  }

  get iconClass() {
    return 'iconoir-windows'
  }

  get iconColor() {
    return 'muted-blue'
  }

  getSummary(integration) {
    if (!integration.has_refresh_token) {
      return this.app.$i18n.t('microsoftIntegrationType.notConnected')
    }
    return this.app.$i18n.t('microsoftIntegrationType.connectedAs', {
      account: integration.account_email || '…',
    })
  }

  get formComponent() {
    return MicrosoftForm
  }

  getDefaultValues() {
    return { client_id: '', tenant: 'common' }
  }

  getOrder() {
    return 40
  }
}
