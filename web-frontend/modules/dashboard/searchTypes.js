import { BaseSearchType } from '@baserow/modules/core/search/types/base'

export class DashboardSearchType extends BaseSearchType {
  constructor(context = {}) {
    super(context)
    this.type = 'dashboard'
    this.name = 'Dashboard'
    this.icon = 'baserow-icon-dashboard'
    this.priority = 3
  }

  _getApplicationId(result) {
    const id = parseInt(result?.metadata?.application_id || result?.id)
    return isNaN(id) ? null : id
  }

  buildUrl(result, context = null) {
    const appId = this._getApplicationId(result)
    if (!appId) {
      return null
    }
    return {
      name: 'dashboard-application',
      params: { dashboardId: appId },
    }
  }

  isNavigable(result, context = null) {
    return this._getApplicationId(result) !== null
  }
}
