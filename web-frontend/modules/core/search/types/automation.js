import { BaseSearchType } from './base'

export class AutomationSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'automation'
    this.name = 'Automation'
    this.icon = 'baserow-icon-automation'
    this.priority = 4
  }

  buildUrl(result, context = null) {
    if (!result.metadata || !result.metadata.application_id) {
      return null
    }

    return `/automation/${result.metadata.application_id}`
  }
}
