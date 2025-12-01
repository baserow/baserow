import { ApplicationType } from '@baserow/modules/core/applicationTypes'
import ApplicationContext from '@baserow/modules/automation/components/application/ApplicationContext'
import AutomationForm from '@baserow/modules/automation/components/form/AutomationForm'
import SidebarComponentAutomation from '@baserow/modules/automation/components/sidebar/SidebarComponentAutomation'
import { populateAutomationWorkflow } from '@baserow/modules/automation/store/automationWorkflow'
import { DEVELOPMENT_STAGES } from '@baserow/modules/core/constants'

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

  delete(application) {
    const { store, router } = this.app
    const workflowSelected = store.getters['automationWorkflow/getWorkflows'](
      application
    ).some((workflow) => workflow._.selected)

    if (workflowSelected) {
      router.push({ name: 'dashboard' })
    }
  }

  async loadExtraData(automation) {
    const { store } = this.app
    if (!automation._loadedOnce) {
      await Promise.all([
        store.dispatch('integration/fetch', {
          application: automation,
        }),
      ])

      await store.dispatch('application/forceUpdate', {
        application: automation,
        data: { _loadedOnce: true },
      })
    }
  }

  populate(application) {
    const values = super.populate(application)
    values.workflows = values.workflows.map(populateAutomationWorkflow)
    if (!values.integrations) {
      values.integrations = []
    }
    if (!values.selectedNodeId) {
      values.selectedNodeId = null
    }
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
        title: i18n.t('applicationType.cantSelectAutomationWorkflowTitle'),
        message: i18n.t(
          'applicationType.cantSelectAutomationWorkflowDescription'
        ),
      })
    }

    return true
  }

  isVisible(application) {
    // Don't show an automation application when the user doesn't
    // have permissions to list workflows.
    return this.app.$hasPermission(
      'automation.list_workflows',
      application,
      application.workspace.id
    )
  }

  get developmentStage() {
    return DEVELOPMENT_STAGES.BETA
  }

  getOrder() {
    return 90
  }
}
