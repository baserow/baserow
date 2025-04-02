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
    const { router, store, i18n } = this.app

    const workflows =
      store.getters['automationWorkflow/getWorkflows'](application)

    if (workflows.length > 0) {
      await router.push({
        name: 'automation-workflow',
        params: {
          automationId: application.id,
          workflowId: workflows[0].id,
        },
      })
      return true
    } else {
      store.dispatch('toast/error', {
        title: i18n.t('applicationType.cantSelectPageTitle'),
        message: i18n.t('applicationType.cantSelectPageDescription'),
      })
      return false
    }
  }

  isBeta() {
    return true
  }

  getOrder() {
    return 90
  }
}
