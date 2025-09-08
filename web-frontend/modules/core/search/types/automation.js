import { BaseSearchType } from './base'
import { AutomationApplicationType } from '@baserow/modules/automation/applicationTypes'

export class AutomationSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'automation'
    this.name = 'Automation'
    this.icon = new AutomationApplicationType().getIconClass()
    this.priority = 4
  }

  buildUrl(result, context = null) {
    if (!result.metadata || !result.metadata.application_id) {
      return null
    }

    return `/automation/${result.metadata.application_id}`
  }
}
