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

  isJobPartOfApplication(job, application) {
    return job.data_sync?.database_id === application.id
  }

  async onJobDone(job) {
    const { $store: store } = this.app
    await store.dispatch('job/forceDelete', job)
  }

  async onJobFailed(job) {
    const { $store: store } = this.app
    await store.dispatch('job/forceDelete', job)
  }

  async onJobCancelled(job) {
    const { $store: store } = this.app
    await store.dispatch('job/forceDelete', job)
  }
}

export class FileImportJobType extends JobType {
  static getType() {
    return 'file_import'
  }

  getName() {
    return 'fileImport'
  }

  isJobPartOfApplication(job, application) {
    return job.database_id === application.id
  }

  async onJobDone(job) {
    const { $store: store } = this.app
    await store.dispatch('job/forceDelete', job)
  }

  async onJobFailed(job) {
    const { $store: store } = this.app
    await store.dispatch('job/forceDelete', job)
  }

  async onJobCancelled(job) {
    const { $store: store } = this.app
    await store.dispatch('job/forceDelete', job)
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

// A job that never reaches a final state (its worker died, it stays started
// until the job cleanup fails it) would otherwise leave the button spinning
// and refusing clicks until the page is reloaded.
export const DISPATCH_JOB_DEADLINE_MS = 5 * 60 * 1000

const FINAL_STATES = ['finished', 'failed', 'cancelled']

// Clicks waiting on their job, by job id. The button mixin keeps its own
// state outside any component, so this lives here rather than in one.
const waitingClicks = new Map()

export class ButtonFieldDispatchJobType extends JobType {
  static getType() {
    return 'button_field_dispatch'
  }

  getName() {
    return 'button_field_dispatch'
  }

  /**
   * A promise for the click's outcome: the finished job's data, or a
   * rejection with the failed job's data. The job store polls the job and
   * `afterUpdate` settles this once it is final.
   */
  static waitFor(job) {
    return new Promise((resolve, reject) => {
      waitingClicks.set(job.id, { resolve, reject })
    })
  }

  /**
   * Stops tracking a click's job, without settling its promise. Used when a
   * click gives up on a job that never reached a final state in time, so a
   * late poll of that job finds no one waiting on it any more.
   */
  static forget(job) {
    waitingClicks.delete(job.id)
  }

  /**
   * A job past the deadline a click waits for counts as ended, so a job whose
   * worker died does not keep its button spinning.
   */
  static hasEnded(job) {
    return (
      FINAL_STATES.includes(job.state) ||
      !(Date.now() - Date.parse(job.created_on) < DISPATCH_JOB_DEADLINE_MS)
    )
  }

  /** Whether the job is a click on this cell that has not ended yet. */
  static isRunningOn(job, fieldId, rowId) {
    return (
      job.type === ButtonFieldDispatchJobType.getType() &&
      job.field_id === fieldId &&
      job.row_id === rowId &&
      !ButtonFieldDispatchJobType.hasEnded(job)
    )
  }

  static settle(job, settle) {
    const waiting = waitingClicks.get(job.id)
    if (waiting) {
      waitingClicks.delete(job.id)
      settle(waiting)
    }
  }

  async onJobDone(job, data) {
    ButtonFieldDispatchJobType.settle(job, ({ resolve }) => resolve(data))
  }

  async onJobFailed(job, data) {
    ButtonFieldDispatchJobType.settle(job, ({ reject }) => reject(data))
  }

  async onJobCancelled(job, data) {
    ButtonFieldDispatchJobType.settle(job, ({ reject }) => reject(data))
  }

  /**
   * A job no click waits on, loaded into the store after a page reload, is
   * dropped once it ends or passes the deadline, which stops its button
   * spinning. The page it was clicked on is gone, so its client actions and
   * any error are not shown.
   */
  async afterUpdate(job, data) {
    const waited = waitingClicks.has(job.id)
    await super.afterUpdate(job, data)
    if (!waited && ButtonFieldDispatchJobType.hasEnded(job)) {
      await this.app.$store.dispatch('job/forceDelete', job)
    }
  }

  /**
   * The job left the store without ending, on logout for instance. The click
   * stops waiting on it, silently: the page it was made on is gone.
   */
  beforeDelete(job) {
    ButtonFieldDispatchJobType.settle(job, ({ reject }) =>
      reject(new ButtonFieldDispatchJobDropped())
    )
  }
}

export class ButtonFieldDispatchJobDropped extends Error {
  constructor() {
    super('Button click job dropped')
  }
}
