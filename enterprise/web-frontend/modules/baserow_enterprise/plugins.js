import { BaserowPlugin } from '@baserow/modules/core/plugins'
import ChatwootSupportSidebarWorkspace from '@baserow_enterprise/components/ChatwootSupportSidebarWorkspace'
import AuditLogSidebarWorkspace from '@baserow_enterprise/components/AuditLogSidebarWorkspace'
import MemberRolesApplicationContextItem from '@baserow_enterprise/components/member-roles/MemberRolesApplicationContextItem'
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
      databaseComponents.push(MemberRolesTableContextItem)
    }
    databaseComponents.push(DateDependencyMenuItem)

    return databaseComponents
  }

  getRightSidebarWorkspaceComponents(workspace) {
    const legacyConfigured =
      !!this.app.$config.public.baserowEnterpriseAssistantLlmModel
    const isConfigured =
      workspace.ai_features?.kuma?.is_enabled ?? legacyConfigured
    return isConfigured ? [AssistantPanel] : []
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
    const customCodeBase =
      mode === 'preview'
        ? `${this.app.$config.public.publicBackendUrl}/api/builder/preview/${builder.id}/custom-code`
        : `${this.app.$config.public.publicBackendUrl}/api/custom_code/${builder.id}`
    const css = `${customCodeBase}/css/${mode === 'preview' ? '' : 'public/'}`
    const js = `${customCodeBase}/js/${mode === 'preview' ? '' : 'public/'}`

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
          tagPosition: 'bodyClose',
        })
      }

      if (s.type === 'stylesheet') {
        script.push({
          rel: 'stylesheet',
          href: s.url,
          crossorigin,
          tagPosition: 'bodyClose',
        })
      }
    })

    if (builder.custom_code.css) {
      link.push({
        rel: 'stylesheet',
        href: css,
        crossorigin: mode === 'preview' ? 'use-credentials' : null,
        tagPosition: 'bodyClose',
      })
    }
    if (builder.custom_code.js) {
      script.push({
        src: js,
        crossorigin: mode === 'preview' ? 'use-credentials' : null,
        defer: true,
        tagPosition: 'bodyClose',
      })
    }

    return {
      link,
      script,
    }
  }
}
