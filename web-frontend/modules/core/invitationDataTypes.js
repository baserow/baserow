import { Registerable } from '@baserow/modules/core/registry'

/**
 * An invitation data type reads the data a backend `InvitationDataType` with the
 * same type adds to every pending workspace invitation, and tells what the
 * invitation is for. The pending invitations list names every target under the
 * email address, in the order of the types.
 */
export class InvitationDataType extends Registerable {
  /**
   * Returns what the invitation is for, as `{ name, description }` targets: the
   * name is shown under the email address, the description in the tooltip that
   * lists all of them.
   *
   * @param {Object} workspace The workspace the invitation belongs to.
   * @param {Object} invitation The pending invitation.
   * @returns {Array<{name: string, description: string}>} The targets.
   */
  getTargets(workspace, invitation) {
    return []
  }
}
