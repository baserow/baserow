import { Registerable } from '@baserow/modules/core/registry'

/**
 * An admin type is visible in the sidebar under the admin menu item. All
 * registered admin types are visible in the sidebar to admins and they clicks
 * on one they are redirected to the route related to the admin type.
 */
export class AdminType extends Registerable {
  /**
   * The icon class name that is used as convenience for the user to
   * recognize admin types. The icon will for example be displayed in the
   * sidebar. If you for example want the database icon, you must return
   * 'database' here. This will result in the classname 'iconoir-database'.
   */
  getIconClass() {
    return null
  }

  /**
   * A human readable name of the admin type. This will be shown in the sidebar
   * if the user is an admin.
   */
  getName() {
    return null
  }

  /**
   * A human readable name of the admin type category. This admin type is grouped by
   * the category in the left sidebar.
   */
  getCategory() {
    const { i18n } = this.app
    return i18n.t('sidebar.general')
  }

  /**
   * The order value used to sort admin types in the sidebar menu.
   */
  getOrder() {
    return 0
  }

  getRouteName() {
    throw new Error('The route name of an admin type must be set.')
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.iconClass = this.getIconClass()
    this.routeName = this.getRouteName()

    if (this.type === null) {
      throw new Error('The type name of an admin type must be set.')
    }
    if (this.iconClass === null) {
      throw new Error('The icon class of an admin type must be set.')
    }
    if (this.name === null) {
      throw new Error('The name of an admin type must be set.')
    }
  }

  /**
   * @return object
   */
  serialize() {
    return {
      type: this.type,
      iconClass: this.iconClass,
      name: this.getName(),
      routeName: this.routeName,
    }
  }

  /**
   * Indicates if the admin type is disabled.
   */
  isDeactivated() {
    return false
  }

  /**
   * Opens this modal if the user clicks on the item in the menu when it's disabled.
   */
  getDeactivatedModal() {
    return null
  }
}

export class DashboardAdminType extends AdminType {
  static getType() {
    return 'dashboard'
  }

  getIconClass() {
    return 'iconoir-home-simple'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('adminType.dashboard')
  }

  getRouteName() {
    return 'admin-dashboard'
  }

  getOrder() {
    return 1
  }
}

export class UsersAdminType extends AdminType {
  static getType() {
    return 'users'
  }

  getIconClass() {
    return 'iconoir-community'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('adminType.users')
  }

  getCategory() {
    const { i18n } = this.app
    return i18n.t('sidebar.people')
  }

  getRouteName() {
    return 'admin-users'
  }

  getOrder() {
    return 2
  }
}

export class WorkspacesAdminType extends AdminType {
  static getType() {
    return 'workspaces'
  }

  getIconClass() {
    return 'baserow-icon-groups'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('adminType.workspaces')
  }

  getCategory() {
    const { i18n } = this.app
    return i18n.t('sidebar.people')
  }

  getRouteName() {
    return 'admin-workspaces'
  }

  getOrder() {
    return 3
  }
}

export class SettingsAdminType extends AdminType {
  static getType() {
    return 'settings'
  }

  getIconClass() {
    return 'iconoir-settings'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('adminType.settings')
  }

  getRouteName() {
    return 'admin-settings'
  }

  getOrder() {
    return 9999
  }
}

export class HealthCheckAdminType extends AdminType {
  static getType() {
    return 'health'
  }

  getIconClass() {
    return 'iconoir-health-shield'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('adminType.health')
  }

  getRouteName() {
    return 'admin-health'
  }

  getOrder() {
    return 10000
  }
}
