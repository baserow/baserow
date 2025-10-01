import { BaseSearchType } from './base'

export class DashboardSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'dashboard'
    this.name = 'Dashboard'
    this.icon = 'baserow-icon-dashboard'
    this.priority = 3
  }

  buildUrl(result, context = null) {
    if (!result.metadata || !result.metadata.application_id) {
      return null
    }

    return `/dashboard/${result.metadata.application_id}`
  }
}
