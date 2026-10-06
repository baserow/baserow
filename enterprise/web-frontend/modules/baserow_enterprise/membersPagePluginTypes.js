import { MembersPagePluginType } from '@baserow/modules/database/membersPagePluginTypes'
import MembersRoleField from '@baserow_enterprise/components/MembersRoleField'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import InvitesRoleField from '@baserow_enterprise/components/InvitesRoleField'
import EnterpriseFeatures from '@baserow_enterprise/features'
import UserTeamsField from '@baserow_enterprise/components/crudTable/fields/UserTeamsField'
import HighestPaidRoleField from '@baserow_enterprise/components/crudTable/fields/HighestPaidRoleField'
import AdminHighestPaidRoleField from '@baserow/modules/core/components/admin/users/fields/HighestPaidRoleField'
import MemberRoleSummaryRows from '@baserow_enterprise/components/member-roles/MemberRoleSummaryRows'

export class EnterpriseMembersPagePluginType extends MembersPagePluginType {
  getMemberRowExpansion() {
    return {
      component: MemberRoleSummaryRows,
      columnKey: 'role_uid',
      isExpandable: (member) =>
        Boolean(member.highest_role_uid) &&
        member.highest_role_uid !== member.role_uid,
    }
  }

  static getType() {
    return 'enterprise_members_columns'
  }

  mutateMembersTableColumns(columns, context) {
    columns = this._replaceRoleColumn(
      columns,
      MembersRoleField,
      'role_uid',
      context
    )

    const insertBeforeColumnIndex = columns.findIndex(
      (column) => column.key === 'two_factor_auth'
    )
    const highestRoleColumn = new CrudTableColumn(
      'highest_role_uid',
      this.app.$i18n.t('membersSettings.membersTable.columns.highestRole'),
      HighestPaidRoleField,
      false,
      false,
      false,
      { workspaceId: context.workspace.id },
      20,
      this.app.$i18n.t(
        'membersSettings.membersTable.columns.highestRoleHelpText'
      )
    )
    const teamsColumn = new CrudTableColumn(
      'teams',
      this.app.$i18n.t('membersSettings.membersTable.columns.teams'),
      UserTeamsField,
      false,
      false,
      false,
      {},
      20
    )
    columns.splice(insertBeforeColumnIndex, 0, highestRoleColumn)
    columns.splice(insertBeforeColumnIndex, 0, teamsColumn)

    return columns
  }

  mutateMembersInvitesTableColumns(columns, context) {
    return this._replaceRoleColumn(
      columns,
      InvitesRoleField,
      'permissions',
      context
    )
  }

  mutateAdminUsersTableColumns(columns, context) {
    const highestRoleColumn = new CrudTableColumn(
      'highest_role_uid',
      this.app.$i18n.t('membersSettings.membersTable.columns.highestRole'),
      AdminHighestPaidRoleField,
      false,
      false,
      false,
      {},
      20,
      this.app.$i18n.t(
        'membersSettings.membersTable.columns.highestRoleInstanceHelpText'
      )
    )
    columns.splice(columns.length - 1, 0, highestRoleColumn)
    return columns
  }

  isDeactivated(workspaceId) {
    return !this.app.$hasFeature(EnterpriseFeatures.RBAC, workspaceId)
  }

  _replaceRoleColumn(columns, FieldComponent, key, { workspace }) {
    const existingRoleColumnIndex = columns.findIndex(
      (column) => column.key === 'permissions'
    )
    if (existingRoleColumnIndex !== -1) {
      columns.splice(
        existingRoleColumnIndex,
        1,
        new CrudTableColumn(
          key,
          this.app.$i18n.t('membersSettings.membersTable.columns.role'),
          FieldComponent,
          true,
          false,
          false,
          {
            workspaceId: workspace.id,
          },
          this.app.$i18n.t('membersPagePlugin.roleHelpText')
        )
      )
    }
    return columns
  }
}
