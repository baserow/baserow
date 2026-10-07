import { Registerable } from '@baserow/modules/core/registry'
import WorkspaceEmailInvite from '@baserow/modules/core/components/workspace/WorkspaceEmailInvite'

/**
 * A method that can be used to invite a member from the common invite modal.
 */
export class InviteType extends Registerable {
  getName() {
    return null
  }

  getIconClass() {
    return null
  }

  getComponent() {
    throw new Error('The component of an invite type must be set.')
  }
}

export class EmailInviteType extends InviteType {
  static getType() {
    return 'email'
  }

  getName() {
    return this.$t('inviteType.email')
  }

  getIconClass() {
    return 'iconoir-mail'
  }

  getComponent() {
    return WorkspaceEmailInvite
  }
}

// Link invitations will use this type when that invite method is implemented.
export class LinkInviteType extends InviteType {
  static getType() {
    return 'link'
  }

  getName() {
    return this.$t('inviteType.link')
  }

  getIconClass() {
    return 'iconoir-link'
  }
}
