import { InvitationRouteType } from '@baserow/modules/core/invitationRouteTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import MemberInvitationRoute from '@baserow_enterprise/components/invitation/MemberInvitationRoute'

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
