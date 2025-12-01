import { JobType } from '@baserow/modules/core/jobTypes'

export class GenerateAIValuesJobType extends JobType {
  static getType() {
    return 'generate_ai_values'
  }

  getIconClass() {
    return 'iconoir-magic-wand'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('jobType.generateAIValues')
  }

  /**
   * Clear pending field operations when job completes (success or failure).
   * This ensures spinners are removed from cells even if job was cancelled.
   */
  async _clearPendingOperations(job) {
    const { store } = this.app
    // If the job has row_ids, clear pending state for those specific rows
    if (job.row_ids && job.row_ids.length > 0 && job.field_id) {
      // We need to find all store prefixes that might have this pending state
      // Grid views typically use 'page/view/grid' as the store prefix
      const storePrefix = 'page/'
      try {
        await store.dispatch(
          `${storePrefix}view/grid/setPendingFieldOperations`,
          {
            fieldId: job.field_id,
            rowIds: job.row_ids,
            value: false,
          }
        )
      } catch (error) {
        // Silently fail if the store action doesn't exist (e.g., not in grid view)
      }
    }
  }

  async onJobDone(job) {
    await this._clearPendingOperations(job)
  }

  async onJobFailed(job) {
    await this._clearPendingOperations(job)
  }

  async onJobCancelled(job) {
    await this._clearPendingOperations(job)
  }
}
