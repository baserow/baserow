import { WorkspaceSettingsPageType } from '@baserow/modules/core/workspaceSettingsPageTypes'
import EnterpriseFeatures from '@baserow_enterprise/features'
import PaidFeaturesModal from '@baserow_premium/components/PaidFeaturesModal'
import { RBACPaidFeature } from '@baserow_enterprise/paidFeatures'

export class TeamsWorkspaceSettingsPageType extends WorkspaceSettingsPageType {
  static getType() {
    return 'teams'
  }

  getName() {
    const { i18n } = this.app
    return i18n.t('teamsSettings.teamsTabTitle')
  }

  /**
   * Responsible for returning whether the user has access to the
   * teams table by checking their `enterprise.teams.list_teams` permission.
   */
  hasPermission(workspace) {
    return this.app.$hasPermission(
      'enterprise.teams.list_teams',
      workspace,
      workspace.id
    )
  }

  /**
   * Responsible for returning whether the user has access to
   * the teams role-based access control feature.
   */
  isFeatureActive(workspace) {
    return this.app.$hasFeature(EnterpriseFeatures.TEAMS, workspace.id)
  }

  getFeatureDeactivatedModal(workspace) {
    return [
      PaidFeaturesModal,
      { 'initial-selected-type': RBACPaidFeature.getType() },
    ]
  }

  getRoute(workspace) {
    return {
      name: 'settings-teams',
      params: {
        workspaceId: workspace.id,
      },
    }
  }
}
