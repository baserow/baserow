import { IdentityExtensionType } from '@baserow/modules/core/identityExtensionTypes'
import CrudTableColumn from '@baserow/modules/core/crudTable/crudTableColumn'
import EnterpriseFeatures from '@baserow_enterprise/features'
import IdentityTeamsCell from '@baserow_enterprise/components/identities/IdentityTeamsCell'
import { getSubjectRoleAssignmentsRowExpansion } from '@baserow_enterprise/utils/subjectRoleAssignments'

export class EnterpriseTeamsIdentityExtensionType extends IdentityExtensionType {
  static getType() {
    return 'enterpriseTeams'
  }

  isActive(workspace) {
    return this.app.$hasFeature(EnterpriseFeatures.TEAMS, workspace.id)
  }

  mutateColumns(columns) {
    return [
      ...columns,
      new CrudTableColumn(
        'teams',
        this.app.$i18n.t('enterpriseIdentities.teams'),
        IdentityTeamsCell
      ),
    ]
  }
}

export class EnterpriseRolesIdentityExtensionType extends IdentityExtensionType {
  static getType() {
    return 'enterpriseRoles'
  }

  isActive(workspace) {
    return this.app.$hasFeature(EnterpriseFeatures.RBAC, workspace.id)
  }

  getRowExpansion() {
    return getSubjectRoleAssignmentsRowExpansion({
      subjectType: 'auth.User',
      columnKey: 'role_uid',
    })
  }
}
