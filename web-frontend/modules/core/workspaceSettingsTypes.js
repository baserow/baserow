import { SettingsType } from '@baserow/modules/core/settingsTypes'
import GenerativeAIWorkspaceSettings from '@baserow/modules/core/components/workspace/GenerativeAIWorkspaceSettings'
import { FF_AI_PROVIDERS } from '@baserow/modules/core/plugins/featureFlags'

export class GenerativeAIWorkspaceSettingsType extends SettingsType {
  static getType() {
    return 'generative-ai'
  }

  getIconClass() {
    return this.app.$featureFlagIsEnabled(FF_AI_PROVIDERS)
      ? 'iconoir-sparks'
      : 'iconoir-magic-wand'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t(
      this.app.$featureFlagIsEnabled(FF_AI_PROVIDERS)
        ? 'workspaceSettingType.aiProviders'
        : 'workspaceSettingType.generativeAI'
    )
  }

  getComponent() {
    return GenerativeAIWorkspaceSettings
  }

  getOrder() {
    return 50
  }
}
