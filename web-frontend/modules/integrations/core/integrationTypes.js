import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import SMTPForm from '@baserow/modules/integrations/core/components/integrations/SMTPForm'

export class SMTPIntegrationType extends IntegrationType {
  static getType() {
    return 'smtp'
  }

  get name() {
    return this.app.$i18n.t('integrationType.smtp')
  }

  get iconClass() {
    return 'iconoir-send-mail'
  }

  get iconColor() {
    return 'muted-red'
  }

  getSummary(integration) {
    return this.app.$i18n.t('smtpIntegrationType.smtpSummary', {
      host: integration.host,
      port: integration.port,
    })
  }

  get formComponent() {
    return SMTPForm
  }

  getDefaultValues() {
    // No `password`: the form starts it at null to mean "untouched", and a
    // default here would overwrite that sentinel on the create path.
    return {
      host: '',
      port: 587,
      use_tls: true,
      username: '',
    }
  }

  getOrder() {
    return 20
  }
}
