import WorkspaceIntegrationsTable from '@baserow/modules/core/components/settings/integrations/WorkspaceIntegrationsTable'
import { SettingsType } from '@baserow/modules/core/settingsTypes'
import AIProviderWorkspaceSettings from '@baserow/modules/core/components/workspace/AIProviderWorkspaceSettings'
import SnapshotsWorkspaceSettings from '@baserow/modules/core/components/workspace/SnapshotsWorkspaceSettings'

export function getEnabledWorkspaceSettings(
  registry,
  workspace,
  canUpdate = true
) {
  return registry
    .getOrderedList('workspaceSettings')
    .filter(
      (setting) =>
        (canUpdate || !setting.requiresWorkspaceUpdatePermission) &&
        setting.isEnabled(workspace) === true
    )
}

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

/** Workspace integrations are listed by members and managed by admins. */
export class IntegrationsWorkspaceSettingsType extends SettingsType {
  requiresWorkspaceUpdatePermission = false

  static getType() {
    return 'integrations'
  }

  getIconClass() {
    return 'iconoir-ev-plug'
  }

  getName() {
    return this.app.$i18n.t('workspaceIntegrations.tabTitle')
  }

  getComponent() {
    return WorkspaceIntegrationsTable
  }

  isEnabled(workspace) {
    return this.app.$hasPermission(
      'workspace.list_integrations',
      workspace,
      workspace.id
    )
  }

  getOrder() {
    return 70
  }
}
