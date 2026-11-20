import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import GoogleGmailSendEmailServiceForm from '@baserow/modules/integrations/google/components/GoogleGmailSendEmailServiceForm'

export const GMAIL_SEND_SCOPE = 'https://www.googleapis.com/auth/gmail.send'
export class GoogleGmailSendEmailServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'google_gmail_send_email'
  }
  get name() {
    return this.app.$i18n.t('googleGmail.name')
  }
  get description() {
    return this.app.$i18n.t('googleGmail.description')
  }
  get icon() {
    return 'iconoir-mail'
  }
  get integrationType() {
    return this.app.$registry.get('integration', 'google')
  }
  get formComponent() {
    return GoogleGmailSendEmailServiceForm
  }
  getDataSchema(service) {
    return service.schema
  }
  getErrorMessage({ service }) {
    if (!service) return null
    if (!service.integration_id)
      return this.app.$i18n.t('googleGmail.integrationRequired')
    if (!service.to_emails?.formula?.length)
      return this.app.$i18n.t('googleGmail.recipientRequired')
    return super.getErrorMessage({ service })
  }
}
