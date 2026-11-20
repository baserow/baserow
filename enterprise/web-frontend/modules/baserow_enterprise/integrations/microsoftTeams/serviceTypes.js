import {
  ServiceType,
  WorkflowActionServiceTypeMixin,
} from '@baserow/modules/core/serviceTypes'
import { MicrosoftIntegrationType } from '@baserow/modules/integrations/microsoft/integrationTypes'
import EnterpriseFeaturesObject from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { MicrosoftTeamsPaidFeature } from '@baserow_enterprise/paidFeatures'
import teamsImage from '@baserow_enterprise/integrations/microsoftTeams/assets/images/teams.svg?url'
import MicrosoftTeamsWriteMessageServiceForm from '@baserow_enterprise/integrations/microsoftTeams/components/services/MicrosoftTeamsWriteMessageServiceForm'
import {
  DESTINATION_ID_FIELDS,
  DESTINATION_TYPE,
  isFormulaEmpty,
} from '@baserow_enterprise/integrations/microsoftTeams/utils'

export class MicrosoftTeamsWriteMessageServiceType extends WorkflowActionServiceTypeMixin(
  ServiceType
) {
  static getType() {
    return 'microsoft_teams_write_message'
  }

  get name() {
    return this.app.$i18n.t('serviceType.microsoftTeamsWriteMessage')
  }

  get description() {
    return this.app.$i18n.t('serviceType.microsoftTeamsWriteMessageDescription')
  }

  get icon() {
    return 'iconoir-chat-lines'
  }

  get image() {
    return teamsImage
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
      service.destination_type === undefined
    ) {
      return null
    }
    if (!service.integration_id) {
      return this.app.$i18n.t('serviceType.microsoftTeamsMissingIntegration')
    }
    const destinationType = service.destination_type || DESTINATION_TYPE.CHANNEL
    for (const field of DESTINATION_ID_FIELDS[destinationType] || []) {
      if (isFormulaEmpty(service[field])) {
        return this.app.$i18n.t(
          destinationType === DESTINATION_TYPE.CHAT
            ? 'serviceType.microsoftTeamsMissingChat'
            : field === 'team_id'
              ? 'serviceType.microsoftTeamsMissingTeam'
              : 'serviceType.microsoftTeamsMissingChannel'
        )
      }
    }
    if (isFormulaEmpty(service.message)) {
      return this.app.$i18n.t('serviceType.microsoftTeamsMissingMessage')
    }
    return super.getErrorMessage({ service })
  }

  isDeactivatedReason({ workspace }) {
    if (!workspace) {
      return null
    }
    if (
      !this.app.$hasFeature(
        EnterpriseFeaturesObject.MICROSOFT_TEAMS,
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
        EnterpriseFeaturesObject.MICROSOFT_TEAMS,
        workspace.id
      )
    ) {
      return [
        PaidFeaturesModal,
        { 'initial-selected-type': MicrosoftTeamsPaidFeature.getType() },
      ]
    }
    return null
  }

  getDataSchema(service) {
    return service.schema
  }

  get formComponent() {
    return MicrosoftTeamsWriteMessageServiceForm
  }

  getOrder() {
    return 9
  }
}
