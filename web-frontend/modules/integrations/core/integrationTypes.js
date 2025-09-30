import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import SMTPForm from '@baserow/modules/integrations/core/components/integrations/SMTPForm'
import slackIntegration from '@baserow/modules/integrations/core/assets/images/slack.svg'
import SlackBotForm from '@baserow/modules/integrations/core/components/integrations/SlackBotForm'

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

export class SlackBotIntegrationType extends IntegrationType {
  static getType() {
    return 'slack_bot'
  }

  get name() {
    return this.app.i18n.t('integrationType.slackBot')
  }

  get image() {
    return slackIntegration
  }

  getSummary(integration) {
    if (!integration.token) {
      return this.app.i18n.t('slackBotIntegrationType.slackBotNoToken')
    }
    return this.app.i18n.t('slackBotIntegrationType.slackBotSummary')
  }

  get formComponent() {
    return SlackBotForm
  }

  getDefaultValues() {
    return { token: '' }
  }

  getOrder() {
    return 10
  }
}
