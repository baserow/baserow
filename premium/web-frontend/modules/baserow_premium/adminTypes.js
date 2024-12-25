import { AdminType } from '@baserow/modules/core/adminTypes'

export class LicensesAdminType extends AdminType {
  static getType() {
    return 'licenses'
  }

  getIconClass() {
    return 'iconoir-shield-check'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('premium.adminType.licenses')
  }

  getCategory() {
    const { i18n } = this.app
    return i18n.t('sidebar.licenses')
  }

  getRouteName() {
    return 'admin-licenses'
  }

  getOrder() {
    return 10000
  }
}
