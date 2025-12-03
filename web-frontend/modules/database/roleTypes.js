import { Registerable } from '@baserow/modules/core/registry'

class RoleType extends Registerable {
  getUid() {
    return null
  }

  getName() {
    return null
  }

  getDescription() {
    return null
  }

  // Indicates weather to show the role as billable/non-billable or show nothing.
  showIsBillable(workspaceId) {
    return false
  }

  // Indicates whether the role is billable.
  getIsBillable() {
    return false
  }

  // Indicates whether the role should be visible in the list.
  isVisible(workspaceId) {
    return true
  }

  // Indicates whether the role is visible, but in a deactivated state.
  isDeactivated(workspaceId) {
    return false
  }

  // The modal component that must be shown when a deactivated role is clicked.
  getDeactivatedClickModal(workspaceId) {
    return null
  }

  // `null` equals all scope types.
  get allowedScopeTypes() {
    return null
  }

  // `null` equals all scope types.
  get allowedSubjectTypes() {
    return null
  }
}

export class AdminRoleType extends RoleType {
  static getType() {
    return 'admin'
  }

  getUid() {
    return 'ADMIN'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('roles.admin.name')
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('roles.admin.description')
  }
}

export class MemberRoleType extends RoleType {
  static getType() {
    return 'member'
  }

  getUid() {
    return 'MEMBER'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('permission.member')
  }

  getDescription() {
    const { i18n } = this.app
    return i18n.t('permission.memberDescription')
  }
}
