import { SettingsType } from '@baserow/modules/core/settingsTypes'
import AIProviderWorkspaceSettings from '@baserow/modules/core/components/workspace/AIProviderWorkspaceSettings'
import SnapshotsWorkspaceSettings from '@baserow/modules/core/components/workspace/SnapshotsWorkspaceSettings'

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

export class SnapshotsWorkspaceSettingsType extends SettingsType {
  static getType() {
    return 'snapshots'
  }

  getIconClass() {
    return 'iconoir-camera'
  }

  getName() {
    const { $i18n: i18n } = this.app
    return i18n.t('workspaceSettingType.snapshots')
  }

  getComponent() {
    return SnapshotsWorkspaceSettings
  }

  /**
   * Only workspace admins can read the snapshot settings.
   */
  isEnabled(workspace) {
    return this.app.$hasPermission(
      'workspace.read_snapshot_settings',
      workspace,
      workspace.id
    )
  }

  getOrder() {
    return 60
  }
}
