import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import ApplicationContext from '@baserow/modules/core/components/application/ApplicationContext'
import AgentBuilderForm from '@baserow_enterprise/agentBuilder/components/AgentBuilderForm'
import AgentBuilderSidebar from '@baserow_enterprise/agentBuilder/components/AgentBuilderSidebar'
import { FF_AGENT_BUILDER } from '@baserow_enterprise/agentBuilder/constants'

export class AgentBuilderApplicationType extends ApplicationType {
  static getType() {
    return 'agent_builder'
  }

  getIconClass() {
    return 'iconoir-sparks'
  }

  getIconColor() {
    return 'purple'
  }

  getName() {
    return this.app.$i18n.t('agentBuilder.applicationName')
  }

  getNamePlural() {
    return this.app.$i18n.t('agentBuilder.applicationNamePlural')
  }

  getDescription() {
    return this.app.$i18n.t('agentBuilder.applicationDescription')
  }

  getApplicationContextComponent() {
    return ApplicationContext
  }

  getApplicationFormComponent() {
    return AgentBuilderForm
  }

  getSidebarComponent() {
    return AgentBuilderSidebar
  }

  canBeCreated() {
    return this.app.$featureFlagIsEnabled(FF_AGENT_BUILDER)
  }

  isVisible(application) {
    return (
      this.canBeCreated() &&
      this.app.$hasPermission(
        'agent_builder.list_agents',
        application,
        application.workspace.id
      )
    )
  }

  populate(application) {
    return { ...application, agents: [] }
  }

  prepareForStoreUpdate(application, data) {
    // Generic application updates don't carry the permission-filtered children.
    return { ...data, agents: application.agents }
  }

  async select(application) {
    if (!this.isVisible(application)) {
      return false
    }
    await this.app.$router.push({
      name: 'agent-builder',
      params: { agentBuilderId: application.id },
    })
    return true
  }

  delete(application) {
    const { $store, $router } = this.app
    if ($store.getters['application/isSelected'](application)) {
      $store.dispatch('agentBuilderAgent/select', null)
      $router.push({
        name: 'workspace',
        params: { workspaceId: application.workspace.id },
      })
    }
  }

  getDependentsName() {
    return [
      this.app.$i18n.t('agentBuilder.agent'),
      this.app.$i18n.t('agentBuilder.agents'),
    ]
  }

  getDependents(application) {
    return (application.agents || []).map((agent) => ({
      id: agent.id,
      name: agent.name,
      iconClass: this.getIconClass(),
    }))
  }
}
