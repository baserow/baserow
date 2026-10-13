import { InvitationTargetType } from '@baserow/modules/core/invitationTargetTypes'
import RoleAssignmentsService from '@baserow_enterprise/services/roleAssignments'
import { filterRoles } from '@baserow_enterprise/utils/roles'

/**
 * Invites people to one object of the workspace: an application, a table or a
 * view. The target is `{ type: 'scope', scopeType, scope }` where `scopeType` is a
 * role assignable scope type and `scope` the object itself. A table target also
 * carries its `database` and a view target its `database` and `table`, so the
 * modal can tell where the object lives. Invitees join the workspace without a
 * workspace role and only get the chosen role on the object.
 */
export class ScopeInvitationTargetType extends InvitationTargetType {
  static getType() {
    return 'scope'
  }

  /**
   * The roles a new person can be invited to the object with. Inviting someone
   * to an object with no access on it is pointless, so that role is left out
   * here; members, teams and agents who already belong to the workspace can
   * still be given it on the object.
   */
  getRoles(workspace, { scopeType }) {
    return filterRoles(workspace._.roles, { scopeType }).filter(
      (role) => role.uid !== 'NO_ACCESS'
    )
  }

  getTitle(workspace, { scope }) {
    return this.$t('scopeInvitationTarget.title', { name: scope.name })
  }

  /**
   * Where the object lives, as "Workspace / Database / Table • Table".
   */
  getSubtitle(workspace, target) {
    const path = [
      workspace.name,
      ...this.getParentNames(target),
      target.scope.name,
    ]
    const typeName = this.getScopeTypeName(target.scopeType, target.scope)
    return `${path.join(' / ')} • ${typeName}`
  }

  getParentNames({ scopeType, database, table }) {
    if (scopeType === 'database_table') {
      return [database?.name].filter(Boolean)
    }
    if (scopeType === 'database_view') {
      return [database?.name, table?.name].filter(Boolean)
    }
    return []
  }

  /**
   * The human readable kind of the scope: "Table", "View", or for an application
   * the name of its type such as "Database" or "Automation".
   */
  getScopeTypeName(scopeType, scope) {
    if (scopeType === 'application') {
      const applicationType = this.app.$registry.exists(
        'application',
        scope.type
      )
        ? this.app.$registry.get('application', scope.type)
        : null
      return (
        applicationType?.getName() ||
        this.$t('scopeInvitationTarget.application')
      )
    }
    const names = {
      database_table: this.$t('scopeInvitationTarget.table'),
      database_view: this.$t('scopeInvitationTarget.view'),
    }
    return names[scopeType] || scopeType
  }

  async sendInvitation(workspace, { scope, scopeType }, values, acceptUrl) {
    const { data } = await RoleAssignmentsService(
      this.app.$client
    ).createScopedInvitation(workspace.id, {
      email: values.email,
      roleUid: values.permissions,
      scopeId: scope.id,
      scopeType,
      baseUrl: acceptUrl,
      captchaToken: values.captchaToken,
    })
    return data
  }
}
