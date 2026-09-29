import { AgentExtensionType } from '@baserow/modules/core/agentExtensionTypes'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import EnterpriseFeatures from '@baserow_enterprise/features'
import AgentTeamsCell from '@baserow_enterprise/components/agents/AgentTeamsCell'

export class EnterpriseTeamsAgentExtensionType extends AgentExtensionType {
  static getType() {
    return 'enterpriseTeams'
  }

  isActive(workspace) {
    return this.app.$hasFeature(EnterpriseFeatures.TEAMS, workspace.id)
  }

  mutateColumns(columns) {
    return [
      ...columns,
      new CrudTableColumn(
        'teams',
        this.app.$i18n.t('enterpriseAgents.teams'),
        AgentTeamsCell
      ),
    ]
  }
}
