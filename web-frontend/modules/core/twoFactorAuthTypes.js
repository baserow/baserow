import { Registerable } from '@baserow/modules/core/registry'

export class TwoFactorAuthType extends Registerable {
  get name() {
    throw new Error('Must be set on the type.')
  }

  /**
   * Returns a description of the given auth type
   */
  get description() {
    return ''
  }

  /**
   * Returns a description for the enabled screen
   */
  get enabledDescription() {
    return ''
  }

  /**
   * Returns side label to be used when selecting
   * providers.
   */
  get sideLabel() {
    return null
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

  get description() {
    return `Use an app to get two-factor authentication codes. We recommend using
        apps such as Google Authenticator, Authy and Microsoft Authenticator.`
  }

  get enabledDescription() {
    return "You'll receive verification codes via an authenticator app. To set up different app or method, simply disable 2FA and setup again."
  }

  get sideLabel() {
    return 'Recommended'
  }

  getOrder() {
    return 0
  }

  get settingsComponent() {
    return null
  }

  get authEnabledSettingsComponent() {
    return null
  }
}
