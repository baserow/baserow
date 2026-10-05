import { SettingsType } from '@baserow/modules/core/settingsTypes'
import AIProviderWorkspaceSettings from '@baserow/modules/core/components/workspace/AIProviderWorkspaceSettings'
import WorkspaceSkillsSettings from '@baserow/modules/core/components/workspace/skills/WorkspaceSkillsSettings'

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

export class SkillsWorkspaceSettingsType extends SettingsType {
  static getType() {
    return 'skills'
  }

  getIconClass() {
    return 'iconoir-book'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('workspaceSettingType.skills')
  }

  getComponent() {
    return WorkspaceSkillsSettings
  }

  getOrder() {
    return 60
  }
}
