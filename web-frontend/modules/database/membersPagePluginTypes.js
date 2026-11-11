import { Registerable } from '@baserow/modules/core/registry'

export class MembersPagePluginType extends Registerable {
  /**
   * Lets a row of the members table expand into more rows below it. Return null
   * for no expansion, or an object with the `component` rendering the rows, which
   * receives the expanded-row slot props of the table, the `workspace` and the
   * props from `getProps(row)`, the `columnKey` of the column the expansion toggle
   * is shown in, `isExpandable(row)` and `getToggleLabel(row)`. Only the first
   * active plugin returning an expansion is used.
   */
  getRowExpansion(context) {
    return null
  }

  /**
   * Lets you manipulate the columns of the members table to either add, remove or
   * modify columns.
   *
   * You could always make sure to not make this function fail hard if it can't update
   * or remove something, since other plugins might have also altered the columns.
   */
  mutateMembersTableColumns(columns, context) {
    return columns
  }

  /**
   * A hook that lets you manipulate the columns of the admin users listing page.
   */
  mutateAdminUsersTableColumns(columns, context) {
    return columns
  }

  /**
   * Set to false in order to enable the plugin
   */
  isDeactivated(workspaceId) {
    return false
  }
}
