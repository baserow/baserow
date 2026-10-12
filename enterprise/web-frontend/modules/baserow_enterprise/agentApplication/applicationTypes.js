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
    return 'iconoir-sparks'
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

  getApplicationContextComponent() {
    return AgentApplicationContext
  }

  getApplicationFormComponent() {
    return AgentApplicationForm
  }

  getSidebarComponent() {
    return AgentApplicationSidebar
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
    if (!this.isVisible(application)) {
      return false
    }
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
