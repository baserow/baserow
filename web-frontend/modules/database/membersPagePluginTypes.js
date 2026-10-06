import { Registerable } from '@baserow/modules/core/registry'

export class MembersPagePluginType extends Registerable {
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
   * Lets you manipulate the columns of the invites table to either add, remove or
   * modify columns.
   *
   * You could always make sure to not make this function fail hard if it can't update
   * or remove something, since other plugins might have also altered the columns.
   */
  mutateMembersInvitesTableColumns(columns, context) {
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
