import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import AgentApplicationContext from '@baserow_enterprise/agentApplication/components/AgentApplicationContext'
import AgentApplicationForm from '@baserow_enterprise/agentApplication/components/AgentApplicationForm'
import AgentApplicationSidebar from '@baserow_enterprise/agentApplication/components/AgentApplicationSidebar'
import { FF_AGENT_BUILDER } from '@baserow_enterprise/agentApplication/constants'

export class AgentApplicationType extends ApplicationType {
  static getType() {
    return 'agent'
  }

  getIconClass() {
    return 'baserow-icon-agent'
  }

  getIconColor() {
    return 'purple'
  }

  getName() {
    return this.app.$i18n.t('agentApplication.applicationName')
  }

  getNamePlural() {
    return this.app.$i18n.t('agentApplication.applicationNamePlural')
  }

  getDescription() {
    return this.app.$i18n.t('agentApplication.applicationDescription')
  }

  supportsTrash() {
    return false
  }

  getApplicationContextComponent() {
    return AgentApplicationContext
  }

  getApplicationFormComponent() {
    return AgentApplicationForm
  }

  getSidebarComponent() {
    return AgentApplicationSidebar
  }

  getOrder() {
    return 100
  }

  canBeCreated() {
    return this.app.$featureFlagIsEnabled(FF_AGENT_BUILDER)
  }

  isVisible(application) {
    return this.app.$hasPermission(
      'application.read',
      application,
      application.workspace.id
    )
  }

  async select(application) {
    // The route loads workspace permissions before checking application access.
    // They are not loaded yet when opening from All workspaces.
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
