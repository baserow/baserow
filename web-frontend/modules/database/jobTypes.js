import { JobType } from '@baserow/modules/core/jobTypes'

import SidebarItemPendingJob from '@baserow/modules/core/components/sidebar/SidebarItemPendingJob.vue'

export class DuplicateTableJobType extends JobType {
  static getType() {
    return 'duplicate_table'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('duplicateTableJobType.name')
  }

  getSidebarText(job) {
    const { $i18n: i18n } = this.app
    return i18n.t('duplicateTableJobType.duplicating') + '...'
  }

  getSidebarComponent() {
    return SidebarItemPendingJob
  }

  isJobPartOfApplication(job, application) {
    return job.original_table.database_id === application.id
  }

  async onJobFailed(job) {
    const { $i18n: i18n, $store: store } = this.app

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
    const { $i18n: i18n, $store: store } = this.app

    const duplicatedTable = job.duplicated_table
    const database = store.getters['application/get'](
      duplicatedTable.database_id
    )

    await store.dispatch('table/forceUpsert', {
      database,
      data: duplicatedTable,
    })

    store.dispatch('toast/info', {
      title: i18n.t('duplicateTableJobType.duplicatedTitle'),
      message: duplicatedTable.name,
    })

    store.dispatch('job/forceDelete', job)
  }
}

export class SyncDataSyncTableJobType extends JobType {
  static getType() {
    return 'sync_data_sync_table'
  }

  getName() {
    return 'syncDataSyncTable'
  }
}

export class FileImportJobType extends JobType {
  static getType() {
    return 'file_import'
  }

  getName() {
    return 'fileImport'
  }
}

export class DuplicateFieldJobType extends JobType {
  static getType() {
    return 'duplicate_field'
  }

  getName() {
    return 'duplicate_field'
  }
}

export class AirtableJobType extends JobType {
  static getType() {
    return 'airtable'
  }

  getName() {
    return 'airtable'
  }
}
