import { Registerable } from '@baserow/modules/core/registry'
import PasswordSettings from '@baserow/modules/core/components/settings/PasswordSettings'
import AccountSettings from '@baserow/modules/core/components/settings/AccountSettings'
import DeleteAccountSettings from '@baserow/modules/core/components/settings/DeleteAccountSettings'
import EmailSettings from '@baserow/modules/core/components/settings/EmailSettings'
import EmailNotifications from '@baserow/modules/core/components/settings/EmailNotifications'
import McpEndpointSettings from '@baserow/modules/core/components/settings/McpEndpointSettings.vue'
import TwoFactorAuthSettings from '@baserow/modules/core/components/settings/TwoFactorAuthSettings.vue'

/**
 * All settings types will be added to the settings modal.
 */
export class SettingsType extends Registerable {
  /**
   * The icon class name that is used as convenience for the user to
   * recognize setting types. The icon will for example be displayed in the modal
   * setting sidebar. If you for example want the database icon, you must return
   * 'database' here. This will result in the classname 'iconoir-database'.
   */
  getIconClass() {
    return null
  }

  /**
   * A human readable name of the settings type. This will be shown in the modal
   * settings sidebar.
   */
  getName() {
    return null
  }

  /**
   * The component will be rendered when the user clicks on the item in the settings
   * model.
   */
  getComponent() {
    throw new Error('The component of a settings type must be set.')
  }

  isEnabled() {
    return true
  }

  constructor(...args) {
    super(...args)
    this.type = this.getType()
    this.iconClass = this.getIconClass()

    if (this.type === null) {
      throw new Error('The type name of a settings type must be set.')
    }
    if (this.iconClass === null) {
      throw new Error('The icon class of a settings type must be set.')
    }
    if (this.name === null) {
      throw new Error('The name of a settings type must be set.')
    }
  }

  /**
   * @return object
   */
  serialize() {
    return {
      type: this.type,
      iconClass: this.iconClass,
      name: this.getName(),
    }
  }

  getOrder() {
    return 50
  }
}

export class AccountSettingsType extends SettingsType {
  static getType() {
    return 'account'
  }

  getIconClass() {
    return 'iconoir-user'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('settingType.account')
  }

  getComponent() {
    return AccountSettings
  }
}

export class PasswordSettingsType extends SettingsType {
  static getType() {
    return 'password'
  }

  getIconClass() {
    return 'iconoir-lock'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('settingType.password')
  }

  isEnabled() {
    return (
      this.app.store.getters['authProvider/getPasswordLoginEnabled'] ||
      this.app.store.getters['auth/isStaff']
    )
  }

  getComponent() {
    return PasswordSettings
  }
}

export class EmailSettingsType extends SettingsType {
  static getType() {
    return 'change_email'
  }

  getIconClass() {
    return 'iconoir-at-sign'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('settingType.email')
  }

  isEnabled() {
    return this.app.store.getters['authProvider/getPasswordLoginEnabled']
  }

  getComponent() {
    return EmailSettings
  }
}

export class EmailNotificationsSettingsType extends SettingsType {
  static getType() {
    return 'email-notifications'
  }

  getIconClass() {
    return 'iconoir-mail'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('settingType.emailNotifications')
  }

  getComponent() {
    return EmailNotifications
  }
}

export class TwoFactorAuthSettingsType extends SettingsType {
  static getType() {
    return 'two-factor-auth'
  }

  getIconClass() {
    return 'baserow-icon-password-check'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('settingType.twoFactorAuth')
  }

  getComponent() {
    return TwoFactorAuthSettings
  }
}

export class MCPEndpointSettingsType extends SettingsType {
  static getType() {
    return 'mcp-endpoint'
  }

  getIconClass() {
    return 'iconoir-magic-wand'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('settingType.mcpEndpoint')
  }

  getComponent() {
    return McpEndpointSettings
  }
}

export class DeleteAccountSettingsType extends SettingsType {
  static getType() {
    return 'delete-account'
  }

  getIconClass() {
    return 'iconoir-cancel'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('settingType.deleteAccount')
  }

  getComponent() {
    return DeleteAccountSettings
  }

  getOrder() {
    return 60
  }
}
