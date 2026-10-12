import { Registerable } from '@baserow/modules/core/registry'
import WorkspaceService from '@baserow/modules/core/services/workspace'

/**
 * An invitation target is what people are invited to: the workspace itself, or a
 * more specific object that another module registers. The `InviteModal` is opened
 * with a target (`{ type, ... }`) and its invitation routes ask the matching target
 * type which roles to offer, how to send an invitation and where the invitee lands
 * after accepting.
 */
export class InvitationTargetType extends Registerable {
  /**
   * The roles that can be granted through the target, in the shape of
   * `workspace._.roles`.
   *
   * @param {Object} workspace The workspace the modal was opened in.
   * @param {Object} target The target the modal was opened with.
   */
  getRoles(workspace, target) {
    throw new Error('The roles of an invitation target type must be set.')
  }

  /**
   * An optional title shown above every route of the modal, for targets that
   * need a header of their own such as "Share Projects". Null leaves the header
   * to the routes.
   */
  getTitle(workspace, target) {
    return null
  }

  /**
   * An optional line under the title, for example where the object lives.
   */
  getSubtitle(workspace, target) {
    return null
  }

  /**
   * Sends one email invitation for the target and resolves with the created
   * invitation. `values` holds the `email`, the chosen `permissions` role uid and
   * the `captchaToken`.
   *
   * @param {Object} workspace The workspace the modal was opened in.
   * @param {Object} target The target the modal was opened with.
   * @param {Object} values The submitted form values.
   * @param {string} acceptUrl The public page where the invitation is accepted.
   */
  async sendInvitation(workspace, target, values, acceptUrl) {
    throw new Error(
      'The send invitation of an invitation target type must be set.'
    )
  }

  /**
   * Where the invitee is sent after accepting the invitation with the given token,
   * as a router location. Called before the invitation is accepted, because the
   * invitation is deleted afterwards. Null leaves the decision to the next
   * registered target type, and finally to the workspace page.
   *
   * @param {string} token The signed invitation token from the email.
   * @param {Object} invitation The invitation fetched with the token.
   */
  async getLandingRoute(token, invitation) {
    return null
  }
}

export class WorkspaceInvitationTargetType extends InvitationTargetType {
  static getType() {
    return 'workspace'
  }

  getRoles(workspace) {
    return workspace._.roles.filter((role) => role.isVisible)
  }

  async sendInvitation(workspace, target, values, acceptUrl) {
    const { data } = await WorkspaceService(this.app.$client).sendInvitation(
      workspace.id,
      acceptUrl,
      values
    )
    // Lets the pending invitations table pick up the new row.
    this.app.$bus.$emit('invite-submitted', data)
    return data
  }
}
