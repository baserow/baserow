import { markRaw } from 'vue'
import { AgentConfigurationSectionType } from '@baserow/modules/agent/configurationSectionTypes'
import { CONFIGURATION_SECTION_GROUP } from '@baserow/modules/agent/constants'
import EnterpriseFeatures from '@baserow_enterprise/features'
import AgentParticipationSettings from '@baserow_enterprise/components/agent/AgentParticipationSettings'
import AgentChannelsSection from '@baserow_enterprise/components/agent/AgentChannelsSection'

const ParticipationSettings = markRaw(AgentParticipationSettings)
const ChannelsSection = markRaw(AgentChannelsSection)

/** A section whose features need Advanced or Enterprise in the Agent's workspace. */
class LicensedAgentConfigurationSectionType extends AgentConfigurationSectionType {
  /**
   * @param {object|null} workspace The Agent's workspace.
   * @returns {boolean} Whether its features are available there.
   */
  isLicensed(workspace) {
    return Boolean(
      workspace && this.app.$hasFeature(EnterpriseFeatures.RBAC, workspace.id)
    )
  }
}

export class PermissionsAgentConfigurationSectionType extends LicensedAgentConfigurationSectionType {
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

  getOrder() {
    return 32
  }
}

export class ChannelsAgentConfigurationSectionType extends LicensedAgentConfigurationSectionType {
  static getType() {
    return 'channels'
  }

  get name() {
    return this.$t('agentChannels.section')
  }

  get description() {
    return this.$t('agentChannels.sectionDescription')
  }

  get icon() {
    return 'iconoir-multi-bubble'
  }

  get component() {
    return ChannelsSection
  }

  get group() {
    return CONFIGURATION_SECTION_GROUP.START
  }

  getOrder() {
    return 25
  }
}
