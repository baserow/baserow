import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'
import { IntegrationType } from '@baserow/modules/core/integrationTypes'
import slackIntegration from '@baserow/modules/integrations/slack/assets/images/slack.svg?url'

// Editor controls load together, independently of the published runtime.
const SlackBotForm = lazyComponent(() =>
  import('@baserow/modules/integrations/components/authoringBundle').then(
    (bundle) => bundle.integrationTypesSlackBotForm
  )
)

export class SlackBotIntegrationType extends IntegrationType {
  static getType() {
    return 'slack_bot'
  }

  get name() {
    return this.app.$i18n.t('integrationType.slackBot')
  }

  get image() {
    return slackIntegration
  }

  get iconColor() {
    return 'darker-pink'
  }

  getSummary(integration) {
    // The token itself is write-only and never reaches the browser, so whether
    // one is set can only be read from the flag the API sends in its place.
    if (!integration.has_token) {
      return this.app.$i18n.t('slackBotIntegrationType.slackBotNoToken')
    }
    return this.app.$i18n.t('slackBotIntegrationType.slackBotSummary')
  }

  getErrorMessage(integration) {
    if (!integration.has_token) {
      return this.app.$i18n.t('slackBotIntegrationType.errorNoToken')
    }
    return super.getErrorMessage(integration)
  }

  get formComponent() {
    return SlackBotForm
  }

  get warning() {
    return this.app.$i18n.t('slackBotIntegrationType.slackBotWarning')
  }

  getDefaultValues() {
    // No `token`: the form starts it at null to mean "untouched", and a default
    // here would overwrite that sentinel on the create path.
    return {}
  }

  getOrder() {
    return 10
  }
}
