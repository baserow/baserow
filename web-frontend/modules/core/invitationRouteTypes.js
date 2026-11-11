import { Registerable } from '@baserow/modules/core/registry'
import { FF_RBAC_IMPROVEMENTS } from '@baserow/modules/core/plugins/featureFlags'
import EmailInvitationRoute from '@baserow/modules/core/components/invitation/EmailInvitationRoute'
import LinkInvitationRoute from '@baserow/modules/core/components/invitation/LinkInvitationRoute'

/**
 * An invitation route is one way of inviting people into a workspace. Every
 * registered route is listed as a tab in the left sidebar of the `InviteModal`,
 * and renders its own component in the modal content when selected.
 */
export class InvitationRouteType extends Registerable {
  /**
   * The icon class shown next to the name in the modal sidebar, for example
   * `iconoir-mail`.
   */
  getIconClass() {
    return null
  }

  /**
   * A human readable name of the route, shown in the modal sidebar.
   */
  getName() {
    return null
  }

  /**
   * The component rendered in the modal content when the route is active. It
   * receives the `workspace`, `target` and `targetType` props. Emit `navigate`
   * with another registered invitation target to replace the modal content and
   * offer Back navigation, or `close` when leaving the dialog entirely.
   * Returning remounts the route to refresh its data.
   */
  getComponent() {
    throw new Error('The component of an invitation route type must be set.')
  }

  /**
   * Whether the route is offered for the given workspace and invitation target.
   *
   * @param {Object} workspace The workspace the modal was opened in.
   * @param {Object} target The target the modal was opened with, `{ type, ... }`.
   */
  isEnabled(workspace, target) {
    return true
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.iconClass = this.getIconClass()

    if (this.type === null) {
      throw new Error('The type name of an invitation route type must be set.')
    }
    if (this.iconClass === null) {
      throw new Error('The icon class of an invitation route type must be set.')
    }
  }

  getOrder() {
    return 50
  }
}

/**
 * Invites someone into the workspace by email. Objects inside the workspace get
 * their own route that combines existing members and new email addresses, so this
 * one is only offered for the workspace itself.
 */
export class EmailInvitationRouteType extends InvitationRouteType {
  static getType() {
    return 'email'
  }

  isEnabled(workspace, target) {
    return target.type === 'workspace'
  }

  getIconClass() {
    return 'iconoir-mail'
  }

  getName() {
    return this.$t('inviteModal.emailRoute')
  }

  getComponent() {
    return EmailInvitationRoute
  }

  getOrder() {
    return 10
  }
}

/**
 * Invites people with permanent links that anyone can use to join. Only offered
 * for targets that support links, while the instance lets people sign up through
 * them, and behind the `RBAC_IMPROVEMENTS` feature flag until links are released.
 */
export class LinkInvitationRouteType extends InvitationRouteType {
  static getType() {
    return 'link'
  }

  getIconClass() {
    return 'iconoir-link'
  }

  getName() {
    return this.$t('inviteModal.linkRoute')
  }

  getComponent() {
    return LinkInvitationRoute
  }

  isEnabled(workspace, target) {
    // New people can only sign up from a link when the instance allows signups,
    // or at least signups through invitations.
    const settings = this.app.$store.getters['settings/get']
    const signupsAllowed =
      settings.allow_new_signups ||
      settings.allow_signups_via_workspace_invitations
    return (
      this.app.$featureFlagIsEnabled(FF_RBAC_IMPROVEMENTS) &&
      signupsAllowed &&
      this.app.$registry
        .get('invitationTarget', target.type)
        .supportsInvitationLinks(workspace, target)
    )
  }

  getOrder() {
    return 20
  }
}
