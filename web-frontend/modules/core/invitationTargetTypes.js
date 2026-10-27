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

  /** The target level shown in Back navigation, such as "table" or "workspace". */
  getNavigationLabel(workspace, target) {
    return (
      this.getTitle(workspace, target) ||
      this.$t('common.workspace').toLowerCase()
    )
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
   */
  async sendInvitation(workspace, target, values) {
    throw new Error(
      'The send invitation of an invitation target type must be set.'
    )
  }

  /**
   * Whether people can be invited to the target with a permanent link. When
   * true, the target must implement the invitation link methods below.
   */
  supportsInvitationLinks(workspace, target) {
    return false
  }

  /**
   * Resolves with the invitation links of the target.
   */
  async fetchInvitationLinks(workspace, target) {
    throw new Error(
      'The invitation links of this target type are not supported.'
    )
  }

  /**
   * Creates an invitation link that grants the `permissions` role uid and
   * resolves with it.
   */
  async createInvitationLink(workspace, target, permissions) {
    throw new Error(
      'The invitation links of this target type are not supported.'
    )
  }

  /**
   * Changes the role uid the link grants and resolves with the updated link.
   */
  async updateInvitationLink(workspace, target, invitationLink, permissions) {
    throw new Error(
      'The invitation links of this target type are not supported.'
    )
  }

  async deleteInvitationLink(workspace, target, invitationLink) {
    throw new Error(
      'The invitation links of this target type are not supported.'
    )
  }
}

export class WorkspaceInvitationTargetType extends InvitationTargetType {
  static getType() {
    return 'workspace'
  }

  getRoles(workspace) {
    return workspace._.roles.filter((role) => role.isVisible)
  }

  async sendInvitation(workspace, target, values) {
    const { data } = await WorkspaceService(this.app.$client).sendInvitation(
      workspace.id,
      values
    )
    // Lets the pending invitations table pick up the new row.
    this.app.$bus.$emit('invite-submitted', data)
    return data
  }

  supportsInvitationLinks() {
    return true
  }

  async fetchInvitationLinks(workspace) {
    const { data } = await WorkspaceService(
      this.app.$client
    ).fetchAllInvitationLinks(workspace.id)
    return data
  }

  async createInvitationLink(workspace, target, permissions) {
    const { data } = await WorkspaceService(
      this.app.$client
    ).createInvitationLink(workspace.id, { permissions })
    return data
  }

  async updateInvitationLink(workspace, target, invitationLink, permissions) {
    const { data } = await WorkspaceService(
      this.app.$client
    ).updateInvitationLink(invitationLink.id, { permissions })
    return data
  }

  async deleteInvitationLink(workspace, target, invitationLink) {
    await WorkspaceService(this.app.$client).deleteInvitationLink(
      invitationLink.id
    )
  }
}
