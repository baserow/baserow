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
   * receives the `workspace` prop and must emit `submitted` with the created
   * invitation once it has been sent, so the modal can close.
   */
  getComponent() {
    throw new Error('The component of an invitation route type must be set.')
  }

  /**
   * Whether the route is offered for the given workspace.
   */
  isEnabled(workspace) {
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

export class EmailInvitationRouteType extends InvitationRouteType {
  static getType() {
    return 'email'
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

  isEnabled(workspace) {
    return this.app.$featureFlagIsEnabled(FF_RBAC_IMPROVEMENTS)
  }

  getOrder() {
    return 20
  }
}
