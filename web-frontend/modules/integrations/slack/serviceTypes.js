import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'
import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import { SlackBotIntegrationType } from '@baserow/modules/integrations/slack/integrationTypes'

// Editor controls load together, independently of the published runtime.
const SlackWriteMessageServiceForm = lazyComponent(() =>
  import('@baserow/modules/integrations/components/authoringBundle').then(
    (bundle) => bundle.serviceTypesSlackWriteMessageServiceForm
  )
)

export class SlackWriteMessageServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'slack_write_message'
  }

  get name() {
    return this.app.$i18n.t('serviceType.slackWriteMessage')
  }

  get icon() {
    return 'iconoir-message-text'
  }

  get integrationType() {
    return this.app.$registry.get(
      'integration',
      SlackBotIntegrationType.getType()
    )
  }

  get description() {
    return this.app.$i18n.t('serviceType.slackWriteMessageDescription')
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
    }
    if (!service.integration_id) {
      return this.app.$i18n.t('serviceType.slackWriteMessageMissingIntegration')
    }
    if (!service.channel?.length) {
      return this.app.$i18n.t('serviceType.slackWriteMessageMissingChannel')
    }
    if (!service.text?.formula?.length) {
      return this.app.$i18n.t('serviceType.slackWriteMessageMissingMessage')
    }
    return super.getErrorMessage({ service })
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return SlackWriteMessageServiceForm
  }

  getOrder() {
    return 8
  }
}
