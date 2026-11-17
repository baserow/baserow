import { InvitationTargetType } from '@baserow/modules/core/invitationTargetTypes'
import RoleAssignmentsService from '@baserow_enterprise/services/roleAssignments'
import { filterRoles } from '@baserow_enterprise/utils/roles'
import { RestrictedViewOwnershipType } from '@baserow_enterprise/viewOwnershipTypes'

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

  getNavigationLabel(workspace, { scopeType, scope }) {
    return this.getScopeTypeName(scopeType, scope).toLowerCase()
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

  async sendInvitation(workspace, { scope, scopeType }, values) {
    const { data } = await RoleAssignmentsService(
      this.app.$client
    ).createScopedInvitation(workspace.id, {
      email: values.email,
      roleUid: values.permissions,
      scopeId: scope.id,
      scopeType,
      captchaToken: values.captchaToken,
    })
    // Lets the members page recount its pending invitations, as a new address
    // gets a workspace invitation along with the role on the object.
    this.app.$bus.$emit('invite-submitted', {
      id: data.invitation_id,
      workspace: workspace.id,
      email: data.email,
    })
    return data
  }

  /**
   * Links give their role on the object only. Admins of the workspace and of the
   * object can manage them, which are the people who can open this dialog.
   */
  supportsInvitationLinks(workspace, { scopeType, scope }) {
    return (
      scopeType !== 'database_view' ||
      scope.ownership_type === RestrictedViewOwnershipType.getType()
    )
  }

  async fetchInvitationLinks(workspace, { scope, scopeType }) {
    const { data } = await RoleAssignmentsService(
      this.app.$client
    ).getScopedInvitationLinks(workspace.id, scope.id, scopeType)
    return data
  }

  async createInvitationLink(workspace, { scope, scopeType }, permissions) {
    const { data } = await RoleAssignmentsService(
      this.app.$client
    ).createScopedInvitationLink(workspace.id, {
      permissions,
      scopeId: scope.id,
      scopeType,
    })
    return data
  }

  async updateInvitationLink(workspace, target, invitationLink, values) {
    const { data } = await RoleAssignmentsService(
      this.app.$client
    ).updateScopedInvitationLink(invitationLink.id, values)
    return data
  }

  async deleteInvitationLink(workspace, target, invitationLink) {
    await RoleAssignmentsService(this.app.$client).deleteScopedInvitationLink(
      invitationLink.id
    )
  }

  getInvitationLinkAdminWarning(workspace, { scope }) {
    return this.$t('scopeInvitationTarget.linkAdminWarning', {
      name: scope.name,
    })
  }

  getInvitationLinkDeleteWarning(workspace, { scope }) {
    return this.$t('scopeInvitationTarget.linkDeleteWarning', {
      name: scope.name,
    })
  }
}

/**
 * The members of one team. The target is `{ type: 'team', team }`. Joining a
 * team comes with the team's own role rather than one per member, so there are
 * no roles to choose from.
 */
export class TeamInvitationTargetType extends InvitationTargetType {
  static getType() {
    return 'team'
  }

  getRoles(workspace, target) {
    return []
  }

  getNavigationLabel(workspace, target) {
    return this.$t('teamInvitationTarget.navigationLabel')
  }

  getTitle(workspace, { team }) {
    return this.$t('teamInvitationTarget.title', { name: team.name })
  }

  /**
   * Where the team lives and the role it gives, as "Team in Workspace • Editor".
   */
  getSubtitle(workspace, { team }) {
    const role = workspace._.roles.find(({ uid }) => uid === team.default_role)
    return role
      ? this.$t('teamInvitationTarget.subtitleWithRole', {
          workspace: workspace.name,
          role: role.name,
        })
      : this.$t('teamInvitationTarget.subtitle', { workspace: workspace.name })
  }

  sendInvitation(workspace, target, values) {
    throw new Error('Teams can only be joined by members of the workspace.')
  }
}
