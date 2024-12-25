import { BaserowPlugin } from '@baserow/modules/core/plugins'
import ChatwootSupportSidebarWorkspace from '@baserow_enterprise/components/ChatwootSupportSidebarWorkspace'
import AuditLogSidebarWorkspace from '@baserow_enterprise/components/AuditLogSidebarWorkspace'
import MemberRolesDatabaseContextItem from '@baserow_enterprise/components/member-roles/MemberRolesDatabaseContextItem'
import MemberRolesTableContextItem from '@baserow_enterprise/components/member-roles/MemberRolesTableContextItem'
import EnterpriseFeatures from '@baserow_enterprise/features'
import SnapshotModalWarning from '@baserow_enterprise/components/SnapshotModalWarning'
import EnterpriseSettings from '@baserow_enterprise/components/EnterpriseSettings'
import EnterpriseSettingsOverrideDashboardHelp from '@baserow_enterprise/components/EnterpriseSettingsOverrideDashboardHelp'
import EnterpriseLogo from '@baserow_enterprise/components/EnterpriseLogo'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import ExportWorkspaceModalWarning from '@baserow_enterprise/components/ExportWorkspaceModalWarning.vue'

export class EnterprisePlugin extends BaserowPlugin {
  static getType() {
    return 'enterprise'
  }

  getSidebarWorkspaceComponents(workspace) {
    const sidebarItems = []
    if (!this.app.$config.BASEROW_DISABLE_SUPPORT) {
      sidebarItems.push(ChatwootSupportSidebarWorkspace)
    }
    sidebarItems.push(AuditLogSidebarWorkspace)
    return sidebarItems
  }

  getAdditionalApplicationContextComponents(workspace, application) {
    const additionalComponents = []
    const hasReadRolePermission = this.app.$hasPermission(
      'application.read_role',
      application,
      workspace.id
    )
    if (
      hasReadRolePermission &&
      application.type === DatabaseApplicationType.getType()
    ) {
      additionalComponents.push(MemberRolesDatabaseContextItem)
    }
    return additionalComponents
  }

  getAdditionalTableContextComponents(workspace, table) {
    if (
      this.app.$hasPermission('database.table.read_role', table, workspace.id)
    ) {
      return [MemberRolesTableContextItem]
    } else {
      return []
    }
  }

  getExtraSnapshotModalComponents(workspace) {
    const rbacSupport = this.app.$hasFeature(
      EnterpriseFeatures.RBAC,
      workspace.id
    )
    return rbacSupport ? SnapshotModalWarning : null
  }

  getExtraExportWorkspaceModalComponents(workspace) {
    const rbacSupport = this.app.$hasFeature(
      EnterpriseFeatures.RBAC,
      workspace.id
    )
    return rbacSupport ? ExportWorkspaceModalWarning : null
  }

  getSettingsPageComponents() {
    return [EnterpriseSettings]
  }

  getDashboardHelpComponents() {
    if (this.app.$hasFeature(EnterpriseFeatures.ENTERPRISE_SETTINGS)) {
      return [EnterpriseSettingsOverrideDashboardHelp]
    } else {
      return []
    }
  }

  getLogoComponent() {
    if (this.app.$hasFeature(EnterpriseFeatures.ENTERPRISE_SETTINGS)) {
      return EnterpriseLogo
    } else {
      return null
    }
  }

  getLogoComponentOrder() {
    return 100
  }

  /**
   * This method can be used to hide certain features in `EnterpriseFeatures.vue`.
   * If the array contains `[EnterpriseFeatures.RBAC]`, for example, then that entry
   * will be hidden in the features.
   */
  getVisuallyHiddenFeatures() {
    return []
  }
}
