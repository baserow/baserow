import { BaseSearchType } from '@baserow/modules/core/search/types/base'

export class DashboardSearchType extends BaseSearchType {
  constructor() {
    super()
    this.type = 'dashboard'
    this.name = 'Dashboard'
    this.icon = 'baserow-icon-dashboard'
    this.priority = 3
  }

  buildUrl(result, context = null) {
    const appId = result?.metadata?.application_id || result?.id
    if (!appId) {
      return null
    }
    return `/dashboard/${appId}`
  }
}
