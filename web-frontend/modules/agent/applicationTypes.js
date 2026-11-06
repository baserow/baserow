import { AGENT_APPLICATION_TYPE } from '@baserow/modules/agent/constants'
import { getApplicationComponent } from '@baserow/modules/core/utils/applicationBundles'
import { ApplicationType } from '@baserow/modules/core/applicationTypes'

import { FF_AGENT_BUILDER } from '@baserow/modules/core/plugins/featureFlags'

export class AgentApplicationType extends ApplicationType {
  /** Applications without child navigation open their page from the sidebar. */
  async selectFromSidebar(application) {
    await this.app.$store.dispatch('application/select', application)
    await this.select(application, this.app)
  }

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
    return getApplicationComponent(this.app, 'agent', 'AgentApplicationContext')
  }

  getApplicationFormComponent() {
    return getApplicationComponent(this.app, 'agent', 'AgentApplicationForm')
  }

  getSidebarComponent() {
    return getApplicationComponent(this.app, 'agent', 'AgentApplicationSidebar')
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
