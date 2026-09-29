import { ApplicationLastViewedItemType } from '@baserow/modules/core/lastViewedItemTypes'

export class DashboardLastViewedItemType extends ApplicationLastViewedItemType {
  static getType() {
    return 'dashboard'
  }

  getOrder() {
    return 80
  }

  getApplicationTypeName() {
    return 'dashboard'
  }

  getName() {
    return this.app.$i18n.t('lastViewedItemType.dashboard')
  }

  getParentPath() {
    // The dashboard is the application itself, so there is no parent to name.
    return []
  }

  getRoute(entry) {
    return {
      name: 'dashboard-application',
      params: { dashboardId: entry.item.id },
    }
  }
}
