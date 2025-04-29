import SidebarItemPendingJob from '@baserow/modules/core/components/sidebar/SidebarItemPendingJob'
import { JobType } from '@baserow/modules/core/jobTypes'

export class DuplicatePageJobType extends JobType {
  static getType() {
    return 'duplicate_page'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('duplicatePageJobType.name')
  }

  getSidebarText(job) {
    const { i18n } = this.app
    return i18n.t('duplicatePageJobType.duplicating') + '...'
  }

  getSidebarComponent() {
    return SidebarItemPendingJob
  }

  isJobPartOfApplication(job, application) {
    return job.original_page.builder_id === application.id
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

    const duplicatedPage = job.duplicated_page
    const builder = store.getters['application/get'](duplicatedPage.builder_id)

    await store.dispatch('page/forceCreate', {
      builder,
      page: duplicatedPage,
    })

    store.dispatch('toast/info', {
      title: i18n.t('duplicatePageJobType.duplicatedTitle'),
      message: duplicatedPage.name,
    })

    store.dispatch('job/forceDelete', job)
  }
}

export class PublishBuilderJobType extends JobType {
  static getType() {
    return 'publish_domain'
  }

  getName() {
    return 'publishDomain'
  }
}
