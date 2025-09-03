import { Registerable } from '@baserow/modules/core/registry'

export class TwoFactorAuthType extends Registerable {
  get name() {
    throw new Error('Must be set on the type.')
  }

  /**
   * Returns a description of the given auth type
   */
  getDescription(service, application) {
    return this.name
  }

  getOrder() {
    return 0
  }

  /**
   * The component to setup the auth type.
   */
  get settingsComponent() {
    return null
  }

  /**
   * The component to show when the
   * authentication is enabled.
   */
  get authEnabledSettingsComponent() {
    return null
  }
}
