import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import ApplicationContext from '@baserow/modules/automation/components/application/ApplicationContext'
import AutomationForm from '@baserow/modules/automation/components/form/AutomationForm'
import SidebarComponentAutomation from '@baserow/modules/automation/components/sidebar/SidebarComponentAutomation'

export class AutomationApplicationType extends ApplicationType {
  static getType() {
    return 'automation'
  }

  getIconClass() {
    return 'baserow-icon-automation'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('applicationType.automation')
  }

  getNamePlural() {
    const { i18n } = this.app
    return i18n.t('applicationType.automations')
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('applicationType.automationDesc')
  }

  getDefaultName() {
    const { i18n } = this.app
    return i18n.t('applicationType.automationDefaultName')
  }

  supportsTrash() {
    return false
  }

  getApplicationContextComponent() {
    return ApplicationContext
  }

  getApplicationFormComponent() {
    return AutomationForm
  }

  getSidebarComponent() {
    return SidebarComponentAutomation
  }

  delete(application, { $router }) {
    $router.push({ name: 'dashboard' })
  }

  async select(application, { $router }) {
    try {
      await $router.push({
        name: 'automation-application',
        params: {
          automationId: application.id,
        },
      })
    } catch (error) {
      if (error.name !== 'NavigationDuplicated') {
        throw error
      }
    }
  }

  isBeta() {
    return true
  }

  getOrder() {
    return 90
  }
}
