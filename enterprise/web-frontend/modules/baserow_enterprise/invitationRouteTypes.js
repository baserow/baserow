import { InvitationRouteType } from '@baserow/modules/core/invitationRouteTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import MemberInvitationRoute from '@baserow_enterprise/components/invitation/MemberInvitationRoute'
import TeamMembersInvitationRoute from '@baserow_enterprise/components/invitation/TeamMembersInvitationRoute'

/**
 * The share dialog of one object: gives existing workspace members, teams and
 * agents a role on it, invites new people by email with a role on it only, and
 * lists who has access. Only offered for scope targets with the RBAC feature,
 * since roles on objects need it.
 */
export class MemberInvitationRouteType extends InvitationRouteType {
  static getType() {
    return 'member'
  }

  getIconClass() {
    return 'iconoir-add-user'
  }

  getName() {
    return this.$t('inviteModal.memberRoute')
  }

  getComponent() {
    return MemberInvitationRoute
  }

  isEnabled(workspace, target) {
    return (
      target.type === 'scope' &&
      this.app.$hasFeature(EnterpriseFeatures.RBAC, workspace.id)
    )
  }

  getOrder() {
    return 0
  }
}

/**
 * The members of one team: adds members and agents of the workspace to it and
 * removes them. Only offered for team targets with the teams feature.
 */
export class TeamMembersInvitationRouteType extends InvitationRouteType {
  static getType() {
    return 'team-members'
  }

  getIconClass() {
    return 'iconoir-community'
  }

  getName() {
    return this.$t('teamMembersRoute.name')
  }

  getComponent() {
    return TeamMembersInvitationRoute
  }

  isEnabled(workspace, target) {
    return (
      target.type === 'team' &&
      this.app.$hasFeature(EnterpriseFeatures.TEAMS, workspace.id)
    )
  }

  getOrder() {
    return 0
  }
}
