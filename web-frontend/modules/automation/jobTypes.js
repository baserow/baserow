import SidebarItemPendingJob from '@baserow/modules/core/components/sidebar/SidebarItemPendingJob'
import { JobType } from '@baserow/modules/core/jobTypes'

export class DuplicateAutomationWorkflowJobType extends JobType {
  static getType() {
    return 'duplicate_automation_workflow'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('duplicateAutomationWorkflowJobType.name')
  }

  getSidebarText(job) {
    const { i18n } = this.app
    return i18n.t('duplicateAutomationWorkflowJobType.duplicating') + '...'
  }

  getSidebarComponent() {
    return SidebarItemPendingJob
  }

  isJobPartOfApplication(job, application) {
    return job.original_automation_workflow.automation_id === application.id
  }

  async onJobFailed(job) {
    const { i18n, store } = this.app

    store.dispatch(
      'toast/error',
      {
        title: i18n.t('clientHandler.notCompletedTitle'),
        message: i18n.t('clientHandler.notCompletedDescription'),
      },
      { root: true }
    )
    await store.dispatch('job/forceDelete', job)
  }

  async onJobDone(job) {
    const { i18n, store } = this.app

    const duplicatedWorkflow = job.duplicated_automation_workflow
    const automation = store.getters['application/get'](
      duplicatedWorkflow.automation_id
    )

    await store.dispatch('automationWorkflow/forceCreate', {
      automation,
      workflow: duplicatedWorkflow,
    })

    store.dispatch('toast/info', {
      title: i18n.t('duplicateAutomationWorkflowJobType.duplicatedTitle'),
      message: duplicatedWorkflow.name,
    })

    store.dispatch('job/forceDelete', job)
  }
}

export class PublishAutomationWorkflowJobType extends JobType {
  static getType() {
    return 'publish_automation_workflow'
  }

  getName() {
    return 'publishAutomationWorkflow'
  }
}
