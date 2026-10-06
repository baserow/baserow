import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import ApplicationContext from '@baserow/modules/dashboard/components/application/ApplicationContext'
import { FF_AGENTS } from '@baserow/modules/core/plugins/featureFlags'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick } from '#imports'
import AgentApplicationForm from '@baserow_enterprise/components/agentApplication/AgentApplicationForm'
import SidebarComponentAgent from '@baserow_enterprise/components/agentApplication/SidebarComponentAgent'
import AgentTemplateSidebar from '@baserow_enterprise/components/agentApplication/AgentTemplateSidebar'
import AgentTemplate from '@baserow_enterprise/components/agentApplication/AgentTemplate'

export class AgentApplicationType extends ApplicationType {
  populate(application) {
    const values = super.populate(application)
    // The integration store pushes into this list when an action tool or
    // trigger form creates an integration, so it must exist from the start.
    if (!values.integrations) {
      values.integrations = []
    }
    return values
  }

  static getType() {
    return 'agent'
  }

  getIconClass() {
    return 'baserow-icon-agent'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.agent')
  }

  getNamePlural() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.agents')
  }

  getDescription() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.agentDesc')
  }

  getDefaultName() {
    const { $i18n: i18n } = this.app
    return i18n.t('applicationType.agentDefaultName')
  }

  supportsTrash() {
    return false
  }

  getApplicationContextComponent() {
    return ApplicationContext
  }

  getApplicationFormComponent() {
    return AgentApplicationForm
  }

  getSidebarComponent() {
    return SidebarComponentAgent
  }

  getTemplateSidebarComponent() {
    return AgentTemplateSidebar
  }

  getTemplatesPageComponent() {
    return AgentTemplate
  }

  getTemplatePage(application) {
    return { application }
  }

  delete(application, { $router }) {
    if (application._.selected) {
      $router.push({
        name: 'workspace',
        params: { workspaceId: application.workspace.id },
      })
    }
  }

  async select(application, { $router }) {
    try {
      await $router.push({
        name: 'agent-application',
        params: {
          agentApplicationId: application.id,
        },
      })
      await pageFinished(this.app)
      await nextTick()
    } catch (error) {
      if (error.name !== 'NavigationDuplicated') {
        throw error
      }
    }
    return true
  }

  isVisible(application) {
    return this.app.$featureFlagIsEnabled(FF_AGENTS)
  }

  canBeCreated() {
    return this.app.$featureFlagIsEnabled(FF_AGENTS)
  }

  getOrder() {
    return 95
  }
}
