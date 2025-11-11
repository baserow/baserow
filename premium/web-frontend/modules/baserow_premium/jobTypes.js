import { JobType } from '@baserow/modules/core/jobTypes'

export class RegenerateAIFieldValuesJobType extends JobType {
  static getType() {
    return 'regenerate_ai_field_values'
  }

  getIconClass() {
    return 'iconoir-magic-wand'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('jobType.regenerateAIFieldValues')
  }

  async onJobDone(job) {
    const { i18n, store } = this.app
    store.dispatch('toast/info', {
      title: i18n.t('jobType.regenerateAIFieldValuesCompleted'),
      message: i18n.t('jobType.regenerateAIFieldValuesCompletedMessage'),
    })
  }

  async onJobFailed(job) {
    const { i18n, store } = this.app
    await store.dispatch(
      'toast/error',
      {
        title: i18n.t('clientHandler.notCompletedTitle'),
        message: job.human_readable_error,
      },
      { root: true }
    )
  }
}
