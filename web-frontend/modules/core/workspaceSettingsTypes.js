import { SettingsType } from '@baserow/modules/core/settingsTypes'
import { lazyComponent } from '@baserow/modules/core/utils/lazyComponent'

const AIProviderWorkspaceSettings = lazyComponent(
  () =>
    import('@baserow/modules/core/components/workspace/AIProviderWorkspaceSettings')
)

export class GenerativeAIWorkspaceSettingsType extends SettingsType {
  static getType() {
    return 'generative-ai'
  }

  getIconClass() {
    return 'iconoir-sparks'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('workspaceSettingType.aiProviders')
  }

  getComponent() {
    return AIProviderWorkspaceSettings
  }

  getOrder() {
    return 50
  }
}
