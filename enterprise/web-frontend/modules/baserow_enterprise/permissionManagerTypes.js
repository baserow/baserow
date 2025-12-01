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

const WRITE_FIELD_VALUES_OPERATION_NAME = 'database.table.field.write_values'
const SUBMIT_FORM_VALUES_OPERATION_NAME =
  'database.table.field.submit_anonymous_values'

export class WriteFieldValuesPermissionManagerType extends PermissionManagerType {
  static getType() {
    return 'write_field_values'
  }

  hasPermission(permissions, operation, context, workspaceId) {
    const opNames = new Set([
      WRITE_FIELD_VALUES_OPERATION_NAME,
      SUBMIT_FORM_VALUES_OPERATION_NAME,
    ])
    if (opNames.has(operation)) {
      return !permissions[operation].exceptions.includes(context.id)
    }
  }

  /**
   * Updates the permissions to write field values for the given field in the
   * given workspace. If `canWriteFieldValues` is true, the field will be removed
   * from the exceptions list of the permission manager. If `canWriteFieldValues`
   * is false, the field will be added to the exceptions list of the permission
   * manager if it is not already present.
   */
  updateWritePermissionsForField(
    workspaceId,
    fieldId,
    canWriteFieldValues,
    canSubmitAnonymousValues
  ) {
    const store = this.app.store
    const permissions =
      store.getters['workspace/getAllPermissions'](workspaceId)
    const newPermissions = permissions.map((manager) => {
      if (manager.name !== this.getType()) return manager

      const writePolicy = manager.permissions[WRITE_FIELD_VALUES_OPERATION_NAME]
      let writeExc
      if (canWriteFieldValues) {
        writeExc = writePolicy.exceptions.filter((exc) => exc !== fieldId)
      } else {
        writeExc = Array.from(new Set([...writePolicy.exceptions, fieldId]))
      }

      const submitPolicy =
        manager.permissions[SUBMIT_FORM_VALUES_OPERATION_NAME]
      let submitExc
      if (canSubmitAnonymousValues) {
        submitExc = submitPolicy.exceptions.filter((exc) => exc !== fieldId)
      } else {
        submitExc = Array.from(new Set([...submitPolicy.exceptions, fieldId]))
      }

      return {
        ...manager,
        permissions: {
          [WRITE_FIELD_VALUES_OPERATION_NAME]: {
            ...writePolicy,
            exceptions: writeExc,
          },
          [SUBMIT_FORM_VALUES_OPERATION_NAME]: {
            ...submitPolicy,
            exceptions: submitExc,
          },
        },
      }
    })
    store.commit('workspace/SET_PERMISSIONS', {
      workspaceId,
      permissions: newPermissions,
    })
  }
}
