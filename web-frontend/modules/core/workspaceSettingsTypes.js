import { SettingsType } from '@baserow/modules/core/settingsTypes'
import GenerativeAIWorkspaceSettings from '@baserow/modules/core/components/workspace/GenerativeAIWorkspaceSettings'

export class GenerativeAIWorkspaceSettingsType extends SettingsType {
  static getType() {
    return 'generative-ai'
  }

  getIconClass() {
    return 'iconoir-magic-wand'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('workspaceSettingType.generativeAI')
  }

  getComponent() {
    return GenerativeAIWorkspaceSettings
  }

  getOrder() {
    return 50
  }
}
