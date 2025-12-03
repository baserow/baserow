import { SettingsType } from '@baserow/modules/core/settingsTypes'
import APITokenSettings from '@baserow/modules/database/components/settings/APITokenSettings'

export class APITokenSettingsType extends SettingsType {
  static getType() {
    return 'tokens'
  }

  getIconClass() {
    return 'iconoir-key-alt-plus'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('settingType.tokens')
  }

  getComponent() {
    return APITokenSettings
  }
}
