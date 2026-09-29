import { AdminType } from '@baserow/modules/core/adminTypes'

export class DatabaseViewsAdminType extends AdminType {
  static getType() {
    return 'database-views'
  }

  getIconClass() {
    return 'iconoir-menu'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('adminType.databaseViews')
  }

  getCategory() {
    const { $i18n: i18n } = this.app
    return i18n.t('sidebar.adminContentCategory')
  }

  getRouteName() {
    return 'admin-database-views'
  }

  getOrder() {
    return 50
  }
}
