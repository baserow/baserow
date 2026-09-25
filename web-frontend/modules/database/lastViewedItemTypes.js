import {
  LAST_VIEWED_SUB_TYPE_SEPARATOR,
  LastViewedItemType,
} from '@baserow/modules/core/lastViewedItemTypes'

export class DatabaseViewLastViewedItemType extends LastViewedItemType {
  static getType() {
    return 'database_view'
  }

  getOrder() {
    return 20
  }

  getViewType(viewType) {
    return this.app.$registry.get('view', viewType)
  }

  getName(entry) {
    return this.app.$i18n.t('lastViewedItemType.databaseView', {
      name: this.getViewType(entry.sub_type).getName(),
    })
  }

  getIconClass(entry) {
    return this.getViewTypeIconClass(this.getViewType(entry.sub_type))
  }

  getViewTypeIconClass(viewType) {
    // Views color their own icon, the same way the sidebar renders them.
    return `${viewType.iconClass} ${viewType.colorClass}`
  }

  getFilterOptions() {
    return this.app.$registry.getOrderedList('view').map((viewType) => ({
      value: `${this.getType()}${LAST_VIEWED_SUB_TYPE_SEPARATOR}${viewType.getType()}`,
      name: this.app.$i18n.t('lastViewedItemType.databaseView', {
        name: viewType.getName(),
      }),
      iconClass: this.getViewTypeIconClass(viewType),
    }))
  }

  getParentPath(entry) {
    return [entry.application.name, entry.item.table.name]
  }

  getRoute(entry) {
    return {
      name: 'database-table',
      params: {
        databaseId: entry.application.id,
        tableId: entry.item.table.id,
        viewId: entry.item.id,
      },
    }
  }
}
