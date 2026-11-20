import { markRaw, onMounted, watch } from 'vue'
import { AgentConfigurationSectionType } from '@baserow/modules/agent/configurationSectionTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import AgentParticipationSettings from '@baserow_enterprise/components/agent/AgentParticipationSettings'
import { agentRuleProblems } from '@baserow_enterprise/utils/agentPermissions'

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

  /**
   * @param {object|null} workspace The Agent's workspace.
   * @returns {boolean} Whether the rules apply there.
   */
  isLicensed(workspace) {
    return Boolean(
      workspace && this.app.$hasFeature(EnterpriseFeatures.RBAC, workspace.id)
    )
  }

  /**
   * Loads the rules once the sidebar mounts, never on the server, and again
   * when the permissions change.
   */
  setup(context) {
    onMounted(() =>
      watch(
        [
          () => context.agent?.id,
          () => this.isLicensed(context.workspace),
          () => context.workspace?._?.permissions,
        ],
        ([agentId, licensed]) => {
          if (agentId && licensed) {
            this.app.$store.dispatch('agentParticipationRules/fetch', {
              agentId,
            })
          }
        },
        { immediate: true }
      )
    )
  }

  getErrorMessage(errors, configuration, { agent, workspace, triggers }) {
    if (!agent || !this.isLicensed(workspace)) return ''
    const rules = this.app.$store.getters['agentParticipationRules/get'](
      agent.id
    )?.rules
    return Object.values(
      agentRuleProblems((...args) => this.$t(...args), rules, triggers)
    ).join(' ')
  }

  getOrder() {
    return 32
  }
}
