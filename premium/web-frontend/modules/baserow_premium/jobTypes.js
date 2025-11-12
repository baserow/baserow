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
}
