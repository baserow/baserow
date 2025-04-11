import { PermissionManagerType } from '@baserow/modules/core/permissionManagerTypes'

export class RolePermissionManagerType extends PermissionManagerType {
  static getType() {
    return 'role'
  }

  getRolesTranslations() {
    const { i18n } = this.app

    return {
      ADMIN: {
        name: i18n.t('roles.admin.name'),
        description: i18n.t('roles.admin.description'),
      },
      BUILDER: {
        name: i18n.t('roles.builder.name'),
        description: i18n.t('roles.builder.description'),
      },
      EDITOR: {
        name: i18n.t('roles.editor.name'),
        description: i18n.t('roles.editor.description'),
      },
      COMMENTER: {
        name: i18n.t('roles.commenter.name'),
        description: i18n.t('roles.commenter.description'),
      },
      VIEWER: {
        name: i18n.t('roles.viewer.name'),
        description: i18n.t('roles.viewer.description'),
      },
      NO_ACCESS: {
        name: i18n.t('roles.noAccess.name'),
        description: i18n.t('roles.noAccess.description'),
      },
      NO_ROLE_LOW_PRIORITY: {
        name: i18n.t('roles.noRoleLowPriority.name'),
        description: i18n.t('roles.noRoleLowPriority.description'),
      },
    }
  }

  hasPermission(permissions, operation, context, workspaceId) {
    if (permissions[operation] === undefined) {
      return false
    }

    return (
      (permissions[operation].default &&
        !permissions[operation].exceptions.includes(context.id)) ||
      (!permissions[operation].default &&
        permissions[operation].exceptions.includes(context.id))
    )
  }
}


export class FieldPermissionManagerType extends PermissionManagerType {
  static getType() {
    return 'field'
  }

  getRolesTranslations() {
    const { i18n } = this.app

    return {
      ADMIN: {
        name: i18n.t('roles.admin.name'),
        description: i18n.t('roles.admin.description'),
      },
      BUILDER: {
        name: i18n.t('roles.builder.name'),
        description: i18n.t('roles.builder.description'),
      },
      EDITOR: {
        name: i18n.t('roles.editor.name'),
        description: i18n.t('roles.editor.description'),
      },
      CUSTOM: {
        name: i18n.t('fieldPermissionManager.customRole.name'),
        description: i18n.t('fieldPermissionManager.customRole.description'),
      },
      NOBODY: {
        name: i18n.t('fieldPermissionManager.nobody.name'),
        description: i18n.t('fieldPermissionManager.nobody.description'),
      },
    }
  }

  hasPermission(permissions, operation, context, workspaceId) {
    return true
  }
}
