import { AGENT_APPLICATION_TYPE } from '@baserow/modules/agent/constants'
import { DEVELOPMENT_STAGES } from '@baserow/modules/core/constants'
import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import AgentApplicationContext from '@baserow/modules/agent/components/AgentApplicationContext'
import AgentCreateModal from '@baserow/modules/agent/components/AgentCreateModal'
import AgentApplicationSidebar from '@baserow/modules/agent/components/AgentApplicationSidebar'
import { FF_AGENT_BUILDER } from '@baserow/modules/core/plugins/featureFlags'

export class AgentApplicationType extends ApplicationType {
  static getType() {
    return AGENT_APPLICATION_TYPE
  }

  getIconClass() {
    return 'baserow-icon-agent'
  }

  getIconColor() {
    return 'purple'
  }

  getName() {
    return this.app.$i18n.t('applicationType.agent')
  }

  getNamePlural() {
    return this.app.$i18n.t('applicationType.agents')
  }

  getViewLabel() {
    return this.app.$i18n.t('applicationType.viewAgent')
  }

  getDescription() {
    return this.app.$i18n.t('applicationType.agentDesc')
  }

  supportsTrash() {
    return false
  }

  getApplicationContextComponent() {
    return AgentApplicationContext
  }

  getCreateModalComponent() {
    return AgentCreateModal
  }

  getSidebarComponent() {
    return AgentApplicationSidebar
  }

  get developmentStage() {
    return DEVELOPMENT_STAGES.BETA
  }

  getOrder() {
    return 10
  }

  populate(application) {
    const values = super.populate(application)
    // Its MCP servers, loaded by the connected apps section.
    if (!values.integrations) {
      values.integrations = []
    }
    return values
  }

  canBeCreated() {
    return this.app.$featureFlagIsEnabled(FF_AGENT_BUILDER)
  }

  isVisible(application) {
    return (
      this.canBeCreated() &&
      this.app.$hasPermission(
        'application.read',
        application,
        application.workspace.id
      )
    )
  }

  async select(application) {
    // Workspace permissions load in the route; they aren't loaded yet from All workspaces.
    await this.app.$router.push({
      name: 'agent-application',
      params: { agentId: application.id },
    })
    return true
  }

  delete(application) {
    const { $store, $router } = this.app
    if ($store.getters['application/isSelected'](application)) {
      $router.push({
        name: 'workspace',
        params: { workspaceId: application.workspace.id },
      })
    }
  }
}
