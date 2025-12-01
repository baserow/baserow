import { Registerable } from '@baserow/modules/core/registry'
import GeneralSettings from '@baserow/modules/automation/components/settings/GeneralSettings'
import IntegrationSettings from '@baserow/modules/automation/components/settings/IntegrationSettings'

class AutomationSettingType extends Registerable {
  static getType() {
    return null
  }

  get name() {
    return null
  }

  get icon() {
    return null
  }

  isDeactivated() {
    return false
  }

  get component() {
    return null
  }

  get componentPadding() {
    return true
  }
}

export class GeneralAutomationSettingsType extends AutomationSettingType {
  static getType() {
    return 'general'
  }

  get name() {
    return this.app.i18n.t('builderSettingTypes.generalName')
  }

  get icon() {
    return 'iconoir-settings'
  }

  isDeactivated() {
    return process.env.NODE_ENV !== 'development'
  }

  getOrder() {
    return 1
  }

  get component() {
    return GeneralSettings
  }
}

export class IntegrationsAutomationSettingsType extends AutomationSettingType {
  static getType() {
    return 'integrations'
  }

  get name() {
    return this.app.i18n.t('builderSettingTypes.integrationsName')
  }

  get icon() {
    return 'iconoir-ev-plug'
  }

  getOrder() {
    return 10
  }

  get component() {
    return IntegrationSettings
  }
}
