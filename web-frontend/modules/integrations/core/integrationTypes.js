import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import SMTPForm from '@baserow/modules/integrations/core/components/integrations/SMTPForm'

export class SMTPIntegrationType extends IntegrationType {
  static getType() {
    return 'smtp'
  }

  get name() {
    return this.app.i18n.t('integrationType.smtp')
  }

  get iconClass() {
    return 'iconoir-send-mail'
  }

  getSummary(integration) {
    return this.app.i18n.t('smtpIntegrationType.smtpSummary', {
      host: integration.host,
      port: integration.port,
    })
  }

  get formComponent() {
    return SMTPForm
  }

  getDefaultValues() {
    return {
      host: '',
      port: 587,
      use_tls: true,
      username: '',
      password: '',
    }
  }

  getOrder() {
    return 20
  }
}
