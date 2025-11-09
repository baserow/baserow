import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import SlackWriteMessageServiceForm from '@baserow/modules/integrations/slack/components/services/SlackWriteMessageServiceForm'

export class SlackWriteMessageServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'slack_write_message'
  }

  get name() {
    return this.app.i18n.t('serviceType.slackWriteMessage')
  }

  get description() {
    return this.app.i18n.t('serviceType.slackWriteMessageDescription')
  }

  getErrorMessage({ service }) {
    if (service === undefined) {
      return null
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
