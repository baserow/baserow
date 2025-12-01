import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import slackIntegration from '@baserow/modules/integrations/slack/assets/images/slack.svg'
import SlackBotForm from '@baserow/modules/integrations/slack/components/integrations/SlackBotForm'

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
