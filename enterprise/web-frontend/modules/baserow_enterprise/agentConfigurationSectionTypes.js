import { markRaw } from 'vue'
import { AgentConfigurationSectionType } from '@baserow/modules/agent/configurationSectionTypes'
import { CONFIGURATION_SECTION_GROUP } from '@baserow/modules/agent/constants'
import EnterpriseFeatures from '@baserow_enterprise/features'
import AgentParticipationSettings from '@baserow_enterprise/components/agent/AgentParticipationSettings'

const ParticipationSettings = markRaw(AgentParticipationSettings)

export class PermissionsAgentConfigurationSectionType extends AgentConfigurationSectionType {
  static getType() {
    return 'permissions'
  }

  get name() {
    return this.$t('agentPermissions.section')
  }

  get description() {
    return this.$t('agentPermissions.sectionDescription')
  }

  get icon() {
    return 'iconoir-group'
  }

  get component() {
    return ParticipationSettings
  }

  get group() {
    return CONFIGURATION_SECTION_GROUP.START
  }

  /**
   * @param {object|null} workspace The Agent's workspace.
   * @returns {boolean} Whether the rules apply there.
   */
  isLicensed(workspace) {
    return Boolean(
      workspace && this.app.$hasFeature(EnterpriseFeatures.RBAC, workspace.id)
    )
  }

  getOrder() {
    return 32
  }
}
