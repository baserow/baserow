import { getApplicationComponent } from '@baserow/modules/core/utils/applicationBundles'
import { EnterpriseRuntimePlugin } from '@baserow_enterprise/pluginsRuntime'
import ChatwootSupportSidebarWorkspace from '@baserow_enterprise/components/ChatwootSupportSidebarWorkspace'
import AuditLogSidebarWorkspace from '@baserow_enterprise/components/AuditLogSidebarWorkspace'
import MemberRolesApplicationContextItem from '@baserow_enterprise/components/member-roles/MemberRolesApplicationContextItem'

import EnterpriseFeatures from '@baserow_enterprise/features'
import SnapshotModalWarning from '@baserow_enterprise/components/SnapshotModalWarning'
import EnterpriseSettings from '@baserow_enterprise/components/EnterpriseSettings'
import EnterpriseSettingsOverrideDashboardHelp from '@baserow_enterprise/components/EnterpriseSettingsOverrideDashboardHelp'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import AssistantSidebarItem from '@baserow_enterprise/components/assistant/AssistantSidebarItem'
import AssistantPanel from '@baserow_enterprise/components/assistant/AssistantPanel'
import AssistantDashboardPrompt from '@baserow_enterprise/components/assistant/AssistantDashboardPrompt'
import { isAssistantConfigured } from '@baserow_enterprise/utils/assistant'

import ExportWorkspaceModalWarning from '@baserow_enterprise/components/ExportWorkspaceModalWarning'

export class EnterprisePlugin extends EnterpriseRuntimePlugin {
  static getType() {
    return 'enterprise'
  }

  getSidebarWorkspaceComponents(workspace) {
    const sidebarItems = []
    sidebarItems.push(AssistantSidebarItem)
    if (!this.app.$config.public.baserowDisableSupport) {
      sidebarItems.push(ChatwootSupportSidebarWorkspace)
    }
    sidebarItems.push(AuditLogSidebarWorkspace)
    return sidebarItems
  }

  getAdditionalApplicationContextComponents(workspace, application) {
    const applicationComponents = []
    const hasReadRolePermission = this.app.$hasPermission(
      'application.read_role',
      application,
      workspace.id
    )
    if (hasReadRolePermission) {
      applicationComponents.push(MemberRolesApplicationContextItem)
    }

    return applicationComponents
  }

  getAdditionalApplicationChildContextComponents(workspace, application, item) {
    if (application.type !== DatabaseApplicationType.getType()) {
      return []
    }

    const databaseComponents = []
    if (
      this.app.$hasPermission('database.table.read_role', item, workspace.id)
    ) {
      databaseComponents.push(
        getApplicationComponent(
          this.app,
          'database',
          'MemberRolesTableContextItem'
        )
      )
    }
    databaseComponents.push(
      getApplicationComponent(this.app, 'database', 'DateDependencyMenuItem')
    )

    return databaseComponents
  }

  getRightSidebarWorkspaceComponents(workspace) {
    return isAssistantConfigured(this.app, workspace) ? [AssistantPanel] : []
  }

  getGridViewFieldTypeIconsBefore(workspace, view, field) {
    const out = []
    out.push(
      getApplicationComponent(
        this.app,
        'database',
        'DateDependencyFieldTypeIcon'
      )
    )
    return out
  }

  getAdditionalViewContextComponents(workspace, table, view) {
    const components = []
    if (
      this.app.$hasPermission(
        'database.table.view.read_role',
        view,
        workspace.id
      ) &&
      // Assigning a role to a user on view level only actually does something for
      // the restricted view. So we're only showing the modal there.
      view.ownership_type === 'restricted'
    ) {
      components.push(
        getApplicationComponent(
          this.app,
          'database',
          'MemberRolesViewContextItem'
        )
      )
    }
    components.push(
      getApplicationComponent(this.app, 'database', 'DateDependencyMenuItem')
    )
    return components
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

  getDashboardTopComponents(workspace) {
    // The component decides whether the assistant is available, because that
    // depends on permissions that are loaded after the page first renders.
    return [AssistantDashboardPrompt]
  }

  getDashboardHelpComponents() {
    if (this.app.$hasFeature(EnterpriseFeatures.ENTERPRISE_SETTINGS)) {
      return [EnterpriseSettingsOverrideDashboardHelp]
    } else {
      return []
    }
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
