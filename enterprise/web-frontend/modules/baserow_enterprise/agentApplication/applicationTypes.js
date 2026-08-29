import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import ApplicationContext from '@baserow/modules/dashboard/components/application/ApplicationContext'
import { FF_AGENTS } from '@baserow/modules/core/plugins/featureFlags'
import { pageFinished } from '@baserow/modules/core/utils/routing'
import { nextTick } from '#imports'
import AgentApplicationForm from '@baserow_enterprise/components/agentApplication/AgentApplicationForm'
import SidebarComponentAgent from '@baserow_enterprise/components/agentApplication/SidebarComponentAgent'

export class AgentApplicationType extends ApplicationType {
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

  delete(application, { $router }) {
    $router.push({ name: 'dashboard' })
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
