import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import { MicrosoftIntegrationType } from '@baserow/modules/integrations/microsoft/integrationTypes'
import EnterpriseFeaturesObject from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { MicrosoftOutlookPaidFeature } from '@baserow_enterprise/paidFeatures'
import outlookImage from '@baserow_enterprise/integrations/microsoftOutlook/assets/images/outlook.svg?url'
import MicrosoftOutlookSendEmailServiceForm from '@baserow_enterprise/integrations/microsoftOutlook/components/services/MicrosoftOutlookSendEmailServiceForm'
import { isFormulaEmpty } from '@baserow_enterprise/integrations/microsoftTeams/utils'

export class MicrosoftOutlookSendEmailServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'microsoft_outlook_send_email'
  }

  get name() {
    return this.app.$i18n.t('serviceType.microsoftOutlookSendEmail')
  }

  get description() {
    return this.app.$i18n.t('serviceType.microsoftOutlookSendEmailDescription')
  }

  get icon() {
    return 'iconoir-send-mail'
  }

  get image() {
    return outlookImage
  }

  get integrationType() {
    return this.app.$registry.get(
      'integration',
      MicrosoftIntegrationType.getType()
    )
  }

  getErrorMessage({ service }) {
    if (
      service === undefined ||
      // A published application only receives the public fields of the
      // service, none of which say how it's configured: it's checked in the
      // editor.
      service.to_emails === undefined
    ) {
      return null
    }
    if (!service.integration_id) {
      return this.app.$i18n.t('serviceType.microsoftOutlookMissingIntegration')
    }
    if (isFormulaEmpty(service.to_emails)) {
      return this.app.$i18n.t('serviceType.microsoftOutlookMissingRecipient')
    }
    return super.getErrorMessage({ service })
  }

  isDeactivatedReason({ workspace }) {
    if (!workspace) {
      return null
    }
    if (
      !this.app.$hasFeature(
        EnterpriseFeaturesObject.MICROSOFT_OUTLOOK,
        workspace.id
      )
    ) {
      return this.app.$i18n.t('enterprise.deactivated')
    }
    return null
  }

  getDeactivatedClickModal({ workspace }) {
    if (
      workspace &&
      !this.app.$hasFeature(
        EnterpriseFeaturesObject.MICROSOFT_OUTLOOK,
        workspace.id
      )
    ) {
      return [
        PaidFeaturesModal,
        { 'initial-selected-type': MicrosoftOutlookPaidFeature.getType() },
      ]
    }
    return null
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return MicrosoftOutlookSendEmailServiceForm
  }

  getOrder() {
    return 10
  }
}
