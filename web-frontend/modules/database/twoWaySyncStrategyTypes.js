import { Registerable } from '@baserow/modules/core/registry'

export class TwoWaySyncStrategyType extends Registerable {
  /**
   * Should return a human-readable description how the two-way sync strategy works.
   */
  getDescription() {
    throw new Error(
      'The description of a two way sync strategy type must be set.'
    )
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
  }

  serialize() {
    return {
      type: this.type,
    }
  }

  /**
   * Indicates whether the data sync is deactivated.
   */
  isDeactivated(workspaceId) {
    return false
  }

  /**
   * When the disabled data sync is clicked, this modal will be shown.
   */
  getDeactivatedClickModal() {
    return null
  }
}
