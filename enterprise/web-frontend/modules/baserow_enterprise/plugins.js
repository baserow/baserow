import { BaserowPlugin } from '@baserow/modules/core/plugins'
import ChatwootSupportSidebarWorkspace from '@baserow_enterprise/components/ChatwootSupportSidebarWorkspace'
import AuditLogSidebarWorkspace from '@baserow_enterprise/components/AuditLogSidebarWorkspace'
import MemberRolesDatabaseContextItem from '@baserow_enterprise/components/member-roles/MemberRolesDatabaseContextItem'
import MemberRolesTableContextItem from '@baserow_enterprise/components/member-roles/MemberRolesTableContextItem'
import MemberRolesViewContextItem from '@baserow_enterprise/components/member-roles/MemberRolesViewContextItem'
import EnterpriseFeatures from '@baserow_enterprise/features'
import SnapshotModalWarning from '@baserow_enterprise/components/SnapshotModalWarning'
import EnterpriseSettings from '@baserow_enterprise/components/EnterpriseSettings'
import EnterpriseSettingsOverrideDashboardHelp from '@baserow_enterprise/components/EnterpriseSettingsOverrideDashboardHelp'
import EnterpriseLogo from '@baserow_enterprise/components/EnterpriseLogo'
import { DatabaseApplicationType } from '@baserow/modules/database/applicationTypes'
import AssistantSidebarItem from '@baserow_enterprise/components/assistant/AssistantSidebarItem'
import AssistantPanel from '@baserow_enterprise/components/assistant/AssistantPanel'
import DateDependencyMenuItem from '@baserow_enterprise/components/dateDependency/DateDependencyMenuItem'
import DateDependencyFieldTypeIcon from '@baserow_enterprise/components/dateDependency/DateDependencyFieldTypeIcon'
import ExportWorkspaceModalWarning from '@baserow_enterprise/components/ExportWorkspaceModalWarning'
import { RestrictedViewOwnershipType } from '@baserow_enterprise/viewOwnershipTypes'

export class EnterprisePlugin extends BaserowPlugin {
  static getType() {
    return 'enterprise'
  }

  getSidebarWorkspaceComponents(workspace) {
    const sidebarItems = []
    sidebarItems.push(AssistantSidebarItem)
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

  getRightSidebarWorkspaceComponents(workspace) {
    const rightSidebarItems = []
    rightSidebarItems.push(AssistantPanel)
    return rightSidebarItems
  }

  getAdditionalTableContextComponents(workspace, table) {
    const out = []
    if (
      this.app.$hasPermission('database.table.read_role', table, workspace.id)
    ) {
      out.push(MemberRolesTableContextItem)
    }
    out.push(DateDependencyMenuItem)
    return out
  }

  getGridViewFieldTypeIconsBefore(workspace, view, field) {
    const out = []
    out.push(DateDependencyFieldTypeIcon)
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
      view.ownership_type === RestrictedViewOwnershipType.getType()
    ) {
      components.push(MemberRolesViewContextItem)
    }
    components.push(DateDependencyMenuItem)
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

  /**
   * Adds the custom CSS/JS defined for this builder.
   */
  getBuilderApplicationHeaderAddition({ builder, mode }) {
    const css = `${this.app.$config.PUBLIC_BACKEND_URL}/api/custom_code/${
      builder.id
    }/css/${mode === 'preview' ? '' : 'public/'}`
    const js = `${this.app.$config.PUBLIC_BACKEND_URL}/api/custom_code/${
      builder.id
    }/js/${mode === 'preview' ? '' : 'public/'}`

    const script = []
    const link = []

    builder.scripts.forEach((s) => {
      if (!s.url) {
        return
      }

      const crossorigin =
        s.crossorigin === 'credentials'
          ? 'use-credentials'
          : s.crossorigin === 'anonymous'
          ? 'anonymous'
          : null

      if (s.type === 'javascript') {
        script.push({
          src: s.url,
          crossorigin,
          defer: s.load_type === 'defer',
          async: s.load_type === 'async',
          body: true,
        })
      }

      if (s.type === 'stylesheet') {
        script.push({
          rel: 'stylesheet',
          href: s.url,
          crossorigin,
          body: true,
        })
      }
    })

    if (builder.custom_code.css) {
      link.push({
        rel: 'stylesheet',
        href: css,
        body: true,
      })
    }
    if (builder.custom_code.js) {
      script.push({
        src: js,
        defer: true,
        body: true,
      })
    }

    return {
      link,
      script,
    }
  }
}
