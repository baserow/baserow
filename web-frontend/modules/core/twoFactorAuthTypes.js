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

  getOrder() {
    return 0
  }
}

export class TOTPAuthType extends TwoFactorAuthType {
  static getType() {
    return 'totp'
  }

  get name() {
    return this.app.i18n.t('totpAuthType.name')
  }

  get description() {
    return this.app.i18n.t('totpAuthType.description')
  }

  get enabledDescription() {
    return this.app.i18n.t('totpAuthType.enabledDescription')
  }

  get sideLabel() {
    return this.app.i18n.t('totpAuthType.sideLabel')
  }

  get settingsComponent() {
    return null
  }

  get authEnabledSettingsComponent() {
    return null
  }

  getOrder() {
    return 0
  }
}
