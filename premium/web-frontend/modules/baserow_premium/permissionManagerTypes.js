import { PermissionManagerType } from '@baserow/modules/core/permissionManagerTypes'

export class ViewOwnershipPermissionManagerType extends PermissionManagerType {
  static getType() {
    return 'view_ownership'
  }

  hasPermission(permissions, operation, context, workspaceId) {
    const operationsOnAnExistingViewAllowedIfPersonalViewAndCreatedBy = [
      'database.table.view.create_filter',
      'database.table.view.create_sort',
      'database.table.view.create_decoration',
      'database.table.view.sort.update',
      'database.table.view.sort.delete',
      'database.table.view.update_field_options',
      'database.table.view.update',
      'database.table.view.delete',
      'database.table.view.duplicate',
      'database.table.view.filter.update',
      'database.table.view.filter.delete',
      'database.table.view.decoration.update',
      'database.table.view.decoration.delete',
      'database.table.view.update_default_values',
      'database.table.view.create_group_by',
      'database.table.view.group_by.update',
      'database.table.view.group_by.delete',
      'database.table.view.prioritize_sortings',
      'database.table.view.prioritize_group_bys',
      'database.table.view.create_filter_group',
      'database.table.view.filter_group.update',
      'database.table.view.filter_group.delete',
    ]
    const { $store } = this.app
    const userId = $store.getters['auth/getUserId']
    if (
      operationsOnAnExistingViewAllowedIfPersonalViewAndCreatedBy.includes(
        operation
      ) &&
      context.ownership_type === 'personal'
    ) {
      return context.owned_by_id === userId
    }
  }
}
