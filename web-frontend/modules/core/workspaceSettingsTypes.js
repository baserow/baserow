import { SettingsType } from '@baserow/modules/core/settingsTypes'
import AIProviderWorkspaceSettings from '@baserow/modules/core/components/workspace/AIProviderWorkspaceSettings'
import InvitationLinksTable from '@baserow/modules/core/components/settings/invitationLinks/InvitationLinksTable'
import { FF_RBAC_IMPROVEMENTS } from '@baserow/modules/core/plugins/featureFlags'

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

/**
 * Lists every invitation link of the workspace in one place: the links to the
 * workspace and the links to its objects, like a table or a team. It's there
 * for anyone who can manage at least one kind of link, which every invitation
 * target type decides for its own links.
 */
export class InvitationLinksWorkspaceSettingsType extends SettingsType {
  static getType() {
    return 'invitation-links'
  }

  getIconClass() {
    return 'iconoir-link'
  }

  getName() {
    return this.app.$i18n.t('invitationLinksSettings.tabTitle')
  }

  getComponent() {
    return InvitationLinksTable
  }

  getOrder() {
    return 60
  }

  isEnabled(workspace) {
    if (!workspace || !this.app.$featureFlagIsEnabled(FF_RBAC_IMPROVEMENTS)) {
      return false
    }
    return Object.values(this.app.$registry.getAll('invitationTarget')).some(
      (targetType) => targetType.canManageInvitationLinks(workspace)
    )
  }
}
