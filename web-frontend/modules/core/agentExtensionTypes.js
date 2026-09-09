import { Registerable } from '@baserow/modules/core/registry'

export class AgentExtensionType extends Registerable {
  isActive(workspace) {
    return true
  }

  mutateColumns(columns, context) {
    return columns
  }
}
