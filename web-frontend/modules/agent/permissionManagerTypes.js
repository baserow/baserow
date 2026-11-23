import { PermissionManagerType } from '@baserow/modules/core/permissionManagerTypes'

export class AgentParticipationPermissionManagerType extends PermissionManagerType {
  static getType() {
    return 'agent_participation'
  }

  /** Decides every operation it grants, and only refuses the others. */
  hasPermission(permissions, operation, context) {
    if (operation in permissions.allowed) {
      return permissions.allowed[operation].includes(context?.id)
    }
    if (permissions.denied[operation]?.includes(context?.id)) return false
    return null
  }
}
