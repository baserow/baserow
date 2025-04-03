import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import ApplicationContext from '@baserow/modules/automation/components/application/ApplicationContext'
import AutomationForm from '@baserow/modules/automation/components/form/AutomationForm'
import SidebarComponentAutomation from '@baserow/modules/automation/components/sidebar/SidebarComponentAutomation'
import { populateAutomationWorkflow } from '@baserow/modules/automation/store/automationWorkflow'

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

  populate(application) {
    const values = super.populate(application)
    values.workflows = values.workflows.map(populateAutomationWorkflow)
    return values
  }

  async select(application) {
    const { router } = this.app

    await router.push({
      name: 'automation-application',
      params: {
        automationId: application.id,
      },
    })
    return true
  }

  isBeta() {
    return true
  }

  getOrder() {
    return 90
  }
}
