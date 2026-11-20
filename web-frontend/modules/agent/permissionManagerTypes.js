import { PermissionManagerType } from '@baserow/modules/core/permissionManagerTypes'

export class AgentTriggeredConversationsPermissionManagerType extends PermissionManagerType {
  static getType() {
    return 'agent_triggered_conversations'
  }

  hasPermission(permissions, operation) {
    return permissions.denied_operations.includes(operation) ? false : null
  }
}
