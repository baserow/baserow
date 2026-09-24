import { markRaw } from 'vue'
import { AgentSettingsType } from '@baserow/modules/core/agentSettingsTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import AgentTeamsFormFieldComponent from '@baserow_enterprise/components/agents/AgentTeamsFormField'

const AgentTeamsFormField = markRaw(AgentTeamsFormFieldComponent)

export class EnterpriseTeamsAgentSettingsType extends AgentSettingsType {
  static getType() {
    return 'teams'
  }

  get name() {
    return this.app.$i18n.t('enterpriseAgents.teams')
  }

  get icon() {
    return 'iconoir-community'
  }

  get component() {
    return AgentTeamsFormField
  }

  getOrder() {
    return 10
  }

  isActive(workspace) {
    return this.app.$hasFeature(EnterpriseFeatures.TEAMS, workspace.id)
  }

  getInitialValues(agent) {
    return { team_ids: (agent?.teams || []).map((team) => team.id) }
  }

  getSubmitValues({ team_ids: teamIds }) {
    return { team_ids: teamIds }
  }
}
