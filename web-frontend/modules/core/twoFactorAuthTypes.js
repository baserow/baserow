import { Registerable } from '@baserow/modules/core/registry'

export class TwoFactorAuthType extends Registerable {
  get name() {
    throw new Error('Must be set on the type.')
  }

  /**
   * Returns a description of the given auth type
   */
  get description() {
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

export class TOTPAuthType extends TwoFactorAuthType {
  static getType() {
    return 'totp'
  }

  get name() {
    return 'Authenticator app'
  }

  /**
   * Returns a description of the given auth type
   */
  get description() {
    return "You'll receive verification codes via an authenticator app. To set up different app or method, simply disable 2FA and setup again."
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
