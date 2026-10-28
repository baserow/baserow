import { Registerable } from '@baserow/modules/core/registry'

export class AgentExtensionType extends Registerable {
  isActive(workspace) {
    return true
  }

  mutateColumns(columns, context) {
    return columns
  }

  /**
   * Lets a row of the agents table expand into more rows below it, with the same
   * shape as `MembersPagePluginType.getRowExpansion`. Only the first active
   * extension returning an expansion is used.
   */
  getRowExpansion(context) {
    return null
  }
}
