import { BaseSearchType } from './base'
import { DashboardApplicationType } from '@baserow/modules/dashboard/applicationTypes'

export class DashboardSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'dashboard'
    this.name = 'Dashboard'
    this.icon = new DashboardApplicationType().getIconClass()
    this.priority = 3
  }

  buildUrl(result, context = null) {
    if (!result.metadata || !result.metadata.application_id) {
      return null
    }

    return `/dashboard/${result.metadata.application_id}`
  }
}
